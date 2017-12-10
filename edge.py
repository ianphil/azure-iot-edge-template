import requests
import uuid
import docker
import os
import subprocess
import sys
import json
from pprint import pprint
import argparse
from base64 import b64encode, b64decode
from hashlib import sha256
from time import time
import fnmatch
from hmac import HMAC
from shutil import copyfile
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
if sys.version_info.major >= 3:
    from urllib.parse import quote, urlencode
else:
    from urllib import quote, urlencode

docker_client = docker.from_env()
docker_client.login(registry=os.environ.get("CONTAINER_REGISTRY_SERVER"), username=os.environ.get(
    "CONTAINER_REGISTRY_USERNAME"), password=os.environ.get("CONTAINER_REGISTRY_PASSWORD"))
docker_api = docker.APIClient()

# Utility


def exe_proc(params):
    proc = subprocess.Popen(
        params, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    stdout_data, stderr_data = proc.communicate()
    print(stdout_data)
    if proc.returncode != 0:
        print(stderr_data)
        sys.exit()


def find_files(directory, pattern):
    # find all files in directory that match the pattern.
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                yield filename


def get_iot_hub_sas_token(uri, key, policy_name, expiry=3600):
    ttl = time() + expiry
    sign_key = "%s\n%d" % ((quote(uri)), int(ttl))
    signature = b64encode(
        HMAC(b64decode(key), sign_key.encode("utf-8"), sha256).digest())

    rawtoken = {
        "sr":  uri,
        "sig": signature,
        "se": str(int(ttl))
    }

    if policy_name is not None:
        rawtoken["skn"] = policy_name

    return "SharedAccessSignature " + urlencode(rawtoken)


def get_file_contents(file):
    with open(file, "r") as file:
        return file.read()

# Runtime


def start():
    print("Starting Edge Runtime")
    exe_proc(["iotedgectl", "--verbose",
              os.environ["RUNTIME_VERBOSITY"], "start"])


def stop():
    print("Stopping Edge Runtime")
    exe_proc(["iotedgectl", "--verbose", os.environ["RUNTIME_VERBOSITY"], "stop"])


def setup():
    print("Setting Up Edge Runtime")
    exe_proc(["iotedgectl", "--verbose", os.environ["RUNTIME_VERBOSITY"],
              "setup", "--config-file", os.environ["RUNTIME_CONFIG_FILE"]])


def status():
    print("Getting Edge Runtime Status")
    exe_proc(["iotedgectl", "--verbose", os.environ["RUNTIME_VERBOSITY"],
              "status"])


def logs():
    modules_config = json.load(open(os.environ["MODULES_CONFIG_FILE"]))
    props = modules_config["moduleContent"]["$edgeAgent"]["properties.desired"]

    open_log(props["systemModules"])
    open_log(props["modules"])


def open_log(modules):
    for module in modules:
        os.system(os.environ["LOGS_CMD"].format(module))


def set_container_registry():
    print("Pushing Edge Runtime to Container Registry")
    image_names = ["azureiotedge-agent", "azureiotedge-hub",
                   "azureiotedge-simulated-temperature-sensor"]
    for image_name in image_names:

        microsoft_image_name = "microsoft/{0}:{1}".format(
            image_name, os.environ.get("RUNTIME_TAG"))

        container_registry_image_name = "{0}/{1}:{2}".format(os.environ.get(
            "CONTAINER_REGISTRY_SERVER"), image_name, os.environ.get("RUNTIME_TAG"))

        for line in docker_api.pull(microsoft_image_name, stream=True):
            print(line)

        tag_result = docker_api.tag(
            image=microsoft_image_name, repository=container_registry_image_name)
        print("Tag Result: {0}".format(tag_result))

        # push to container registry
        for line in docker_api.push(repository=container_registry_image_name, stream=True):
            print(line)

    set_container_registry_in_config(image_names)


def set_container_registry_in_config(image_names):
    print("Changing Edge config files to use Container Registry")
    config_dir = "{0}\\config".format(os.getcwd())

    # Get all config files in \config dir.
    config_files = [os.path.join(config_dir, f) for f in os.listdir(
        config_dir) if f.endswith(".json")]

    # Replace microsoft/ with ${CONTAINER_REGISTRY_SERVER}
    for config_file in config_files:
        config_file_contents = get_file_contents(config_file)
        for image_name in image_names:
            config_file_contents = config_file_contents.replace(
                "microsoft/" + image_name, "${CONTAINER_REGISTRY_SERVER}/" + image_name)

        with open(config_file, "w") as config_file_build:
            config_file_build.write(config_file_contents)


def set_config():
    print("Setting Config Files")
    config_dir = "{0}\\config".format(os.getcwd())
    build_config_dir = "build\\config"

    # Create config dir if it doesn't exist
    if not os.path.exists(build_config_dir):
        os.makedirs(build_config_dir)

    # Get all config files in \config dir.
    config_files = [os.path.join(config_dir, f) for f in os.listdir(
        config_dir) if f.endswith(".json")]

    # Expand envars and rewrite to \build\config
    for config_file in config_files:
        with open(config_file, "r") as config_file_stream:
            config_file_expanded = os.path.expandvars(
                config_file_stream.read())

        with open("{0}\\{1}".format(build_config_dir, os.path.basename(config_file)), "w") as config_file_build:
            config_file_build.write(config_file_expanded)

# Modules Functions


def build():
    print("Building Modules")

    # Get all the modules to build as specified in config.
    modules_to_process = [module.strip()
                          for module in os.environ["ACTIVE_MODULES"].split(",")]

    for module in os.listdir("{0}\\modules".format(os.getcwd())):

        if len(modules_to_process) == 0 or modules_to_process[0] == "*" or module in modules_to_process:

            print("Restoring Module {0}".format(module))

            # 1. dotnet restore
            exe_proc(["dotnet", "restore", "modules\\{0}".format(
                module), "-v", os.environ["DOTNET_VERBOSITY"]])

            print("Building Module {0}".format(module))
            # 2. dotnet build

            exe_proc(["dotnet", "build", "modules\\{0}\\{0}.csproj".format(
                module), "-v", os.environ["DOTNET_VERBOSITY"]])

            # 3. Get all docker files in project
            docker_files = find_files("{0}\\modules\\{1}".format(
                os.getcwd(), module), "Dockerfile*")

            # 4. Process each Dockerfile found
            for docker_file in docker_files:
                print(docker_file)
                print("Processing Dockerfile {0}".format(docker_file))

                docker_file_name = os.path.basename(docker_file)
                # assume /Docker/{runtime}/Dockerfile folder structure
                # image name will be the same as the module folder name, filter-module
                # tag will be {runtime}{ext}{container_tag}, i.e. linux-x64-debug-jong
                # runtime is the Dockerfile immediate parent folder name
                # ext is Dockerfile extension for example with Dockerfile.debug, debug is the mod
                # CONTAINER_TAG is env var

                # i.e. when found: filter-module/Docker/linux-x64/Dockerfile.debug and CONTAINER_TAG = jong
                # we'll get: filtermodule:linux-x64-debug-jong

                runtime = os.path.basename(os.path.dirname(docker_file))
                ext = "" if os.path.splitext(docker_file)[
                    1] == "" else "-" + os.path.splitext(docker_file)[1][1:]
                container_tag = "" if os.environ["CONTAINER_TAG"] == "" else "-" + \
                    os.environ["CONTAINER_TAG"]

                tag_name = runtime + ext + container_tag

                # construct the build output path
                build_path = "{0}\\build\\modules\\{1}\\{2}".format(
                    os.getcwd(), module, runtime)
                print(build_path)

                # dotnet publish
                exe_proc(["dotnet", "publish", "modules\\{0}\\{0}.csproj".format(
                    module), "-f", "netcoreapp2.0", "-o", build_path, "-v", os.environ["DOTNET_VERBOSITY"]])

                # copy Dockerfile to publish dir
                build_dockerfile = "{0}\\{1}".format(
                    build_path, docker_file_name)

                copyfile(docker_file, build_dockerfile)

                image_source_name = "{0}:{1}".format(module, tag_name)
                image_destination_name = "{0}/{1}:{2}".format(
                    os.environ.get("CONTAINER_REGISTRY_SERVER"), module, tag_name)

                # cd to the build output to build the docker image
                project_dir = os.getcwd()
                os.chdir(build_path)
                build_result = docker_client.images.build(
                    tag=image_source_name, path=".", dockerfile=docker_file_name)
                print("Docker Build Result: {0}".format(build_result))

                os.chdir(project_dir)

                # tag the image
                tag_result = docker_api.tag(
                    image=image_source_name, repository=image_destination_name)
                print("Docker Tag Result: {0}".format(tag_result))

                # push to container registry
                print("Pushing Docker Images")

                for line in docker_client.images.push(repository=image_destination_name, stream=True):
                    print(line)


def deploy():
    print("Deploying Edge Module Config")
    deploy_device_configuration(
        os.environ.get("IOTHUB_NAME"), os.environ.get("IOTHUB_KEY"),
        os.environ.get("EDGE_DEVICE_ID"), os.environ.get(
            "MODULES_CONFIG_FILE"),
        os.environ.get("IOTHUB_POLICY_NAME"), os.environ.get("IOT_REST_API_VERSION"))

# Docker Functions


def remove_containers():
    print("Removing Containers....")
    containers = docker_client.containers.list(all=True)
    print("Found {0} Containers".format(len(containers)))
    for container in containers:
        print("Removing Container: {0}:{1}".format(
            container.id, container.name))
        container.remove(force=True)
    print("Containers Removed")


def remove_images():
    print("Removing Dangling Images....")
    images = docker_client.images.list(all=True, filters={"dangling": True})
    print("Found {0} Images".format(len(images)))

    for image in images:
        print("Removing Image: {0}".format(str(image.id)))
        docker_client.images.remove(image=image.id, force=True)
    print("Images Removed")

    print("Removing Images....")
    images = docker_client.images.list()
    print("Found {0} Images".format(len(images)))

    for image in images:
        print("Removing Image: {0}".format(str(image.id)))
        docker_client.images.remove(image=image.id, force=True)
    print("Images Removed")


def deploy_device_configuration(iothub_name, iothub_key, device_id, config_file, iothub_policy_name, api_version):
    resource_uri = iothub_name + ".azure-devices.net"
    token_expiration_period = 60
    deploy_uri = "https://{0}/devices/{1}/applyConfigurationContent?api-version={2}".format(
        resource_uri, device_id, api_version)
    iot_hub_sas_token = get_iot_hub_sas_token(
        resource_uri, iothub_key, iothub_policy_name, token_expiration_period)

    deploy_response = requests.post(deploy_uri,
                                    headers={
                                        "Authorization": iot_hub_sas_token,
                                        "Content-Type": "application/json"
                                    },
                                    data=get_file_contents(config_file)
                                    )

    print(deploy_uri)
    print(deploy_response.status_code)
    print(deploy_response.text)

    if deploy_response.status_code == 204:
        print("Configuration successfully applied.  Please run `docker logs edgeAgent -f` to see the change applied.")
    else:
        print("There was an error applying the configuration. You should see an error message above that indicates the issue.")


if __name__ == "__main__":

    def modules(args):
        set_config()
        # Module Commands
        if args.build:
            build()

        if args.deploy:
            deploy()

    def runtime(args):
        set_config()
        # Runtime Commands
        if args.set_container_registry:
            set_container_registry()

        if args.setup:
            setup()

        if args.start:
            start()

        if args.stop:
            stop()

        if args.restart:
            stop()
            setup()
            start()

        if args.status:
            status()

        if args.logs:
            logs()

    def docker(args):
        # Docker Commands
        if args.clean:
            args.remove_containers = True
            args.remove_images = True

        if args.remove_containers:
            remove_containers()

        if args.remove_images:
            remove_images()

    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest="cmd")

    runtimeparser = subparsers.add_parser("runtime")
    runtimeparser.required = False
    runtimeparser.set_defaults(func=runtime)
    runtimeparser.add_argument("--start", help="Starts Edge Runtime",
                               action="store_true", default=False)

    runtimeparser.add_argument("--stop", help="Stops Edge Runtime",
                               action="store_true", default=False)

    runtimeparser.add_argument("--restart", help="Restarts Edge Runtime",
                               action="store_true", default=False)

    runtimeparser.add_argument("--setup", help="Setup Edge Runtime using runtime.json in build/config directory",
                               action="store_true", default=False)

    runtimeparser.add_argument("--status", help="Edge Runtime Status",
                               action="store_true", default=False)

    runtimeparser.add_argument("--logs", help="Edge Runtime Logs",
                               action="store_true", default=False)

    runtimeparser.add_argument("--set-container-registry",
                               help="Pulls Edge Runtime from Docker Hub and pushes to container registry", action="store_true", default=False)

    runtimeparser.add_argument("--set-config", help="Expands env vars in /config and copies to /build/config",
                               action="store_true", default=True)

    modulesparser = subparsers.add_parser("modules")
    modulesparser.set_defaults(func=modules)

    modulesparser.add_argument("--build", help="Builds and pushes modules specified in ACTIVE_MODULES env var to container registry",
                               action="store_true", default=False)

    modulesparser.add_argument("--deploy", help="Deploys modules to Edge device using modules.json in build/config directory",
                               action="store_true", default=False)

    modulesparser.add_argument("--set-config", help="Expands env vars in /config and copies to /build/config",
                               action="store_true", default=True)

    dockerparser = subparsers.add_parser("docker")
    dockerparser.set_defaults(func=docker)

    dockerparser.add_argument("--clean", help="Removes all the Docker containers and Images",
                              action="store_true", default=False)

    dockerparser.add_argument("--remove-containers",
                              help="Removes all the Docker containers", action="store_true", default=False)

    dockerparser.add_argument("--remove-images", help="Removes all the Docker images",
                              action="store_true", default=False)

    if len(sys.argv) == 1:
        parser.print_help()
    else:
        args, extras = parser.parse_known_args()
        # print(args)
        # print(extras)

        if args.cmd:
            args.func(args)
