# Azure IoT Edge Template

This project is a starting point for your Azure IoT Edge development. 

It includes:
 - A script (**edge.py**) that simplifies runtime, modules and docker management.
 - A suggested folder structure for Edge projects including **modules**, **build**, and **config** folders.

## Edge Script
You will find the **edge.py** script in the root of this repository.  It has the following commands:

**runtime**

`edge.py runtime --help`
- `--start`               Starts Edge Runtime
- `--stop`              Stops Edge Runtime
- `--restart`             Restarts Edge Runtime
- `--setup`               Setup Edge Runtime using runtime.json in build/config directory
- `--status`              Edge Runtime Status
- `--logs`                Edge Runtime Logs
- `--set-container-registry` Pulls Edge Runtime from Docker Hub and pushes to container registry
- `--set-config`          Expands env vars in /config and copies to /build/config

**modules**

`edge.py modules --help`
- `--build`       Builds and pushes modules specified in ACTIVE_MODULES env var to container registry
- `--deploy`      Deploys modules to Edge device using modules.json in build/config directory
- `--set-config`  Expands env vars in /config and copies to /build/config

**docker**

`edge.py docker --help`
- `--clean`              Removes all the Docker containers and Images
- `--remove-containers`  Removes all the Docker containers
- `--remove-images`      Removes all the Docker images

## Folder Structure

There are 3 main folders in this project:

1. **config** - Contains sample config files for both modules and runtime.

1. **build** - Contains the files outputted by the .NET Core SDK.

1. **modules** - Contains all of the modules for your Edge project.
    - The edge.py script assumes that you'll structure your Dockerfiles exactly like the filter-module sample.  Have a Docker folder in the root of the project, then subfolders within that to support multiple Docker files.

        > It is important that you follow this structure or the script will not work.

## Setup
### Azure Setup
1. [Create Azure IoT Hub](https://docs.microsoft.com/en-us/azure/iot-hub/iot-hub-csharp-csharp-getstarted#create-an-iot-hub)
1. [Create Azure Container Registry](https://docs.microsoft.com/en-us/azure/container-registry/container-registry-get-started-portal)
    - Make sure you enable Admin Access when you create the Azure Container Registry
1. Create Edge Device using the Azure Portal

You can also deploy the IoT Hub and Container Registry with this deployment script:

<a href="https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fjonbgallant%2Fazure-iot-edge-template%2Fassets%2Fdeploy%2FARMDeployment%2Fazuredeploy.json" target="_blank"><img src="https://azuredeploy.net/deploybutton.png"/></a>


    
### Dev Machine Setup
> Note: This script has been tested with Python 2.7 and Windows as of 12/9/2017. More test coverage coming soon...

1. Install [Docker](https://docs.docker.com/engine/installation/)
1. Install [Python 2.7](https://www.python.org/downloads/)
1. Install [.NET Core SDK](https://www.microsoft.com/net/core#windowscmd)
1. Clone This Repository

    `git clone https://github.com/jonbgallant/azure-iot-edge-template.git project-name`

1. Install Dependencies

    `pip install -r requirements.txt`

1. Set Environment Variables
    - Rename .env.tmp to .env
    - Open .env and set variables

## Usage

Each of the edge.py commands can be run individually or as a group.  Here's how to quickly see how it works.  

### Modules Build and Deploy

```
python edge.py modules --build --deploy
```

The `--build` command will build each module in the `modules` folder and push it to your container registry.  The `--deploy` command will apply the `\build\modules.json` configuration file to your Edge device.

You can configure what modules will be built and deployed using the ACTIVE_MODULES env var in the .env file.

### Runtime Setup and Start

```
python edge.py runtime --setup --start
```
The `--setup` command will apply the `\build\runtime.json` file to your Edge device.  The `--start` command will start the Edge runtime.
   
### Monitor Messages

You can use the [Device Explorer](https://github.com/Azure/azure-iot-sdk-csharp/releases/download/2017-12-2/SetupDeviceExplorer.msi) to monitor the messages that are sent to your IoT Hub.

### Set Container Registry

You can also use the script to host the Edge runtime from your own Azure Container Registry.  Just set the .env values for your Container Registry and run the following command:

```
python edge.py runtime --set-container-registry
```

### View Runtime Logs

The edge.py script also include a "Logs" command that will open a new command prompt for each module it finds in your Edge config.  Just run the following command:

```
python edge.py runtime --logs
```

You can configure the logs command in the .env file with the LOGS_CMD setting.  The .env.tmp file provides two options, one for ConEmu and one for Cmd.exe.

## Issues

Please use the GitHub issues tab to report any issues.

## Contributing

Please fork, branch and pull-request any changes you'd like to make.