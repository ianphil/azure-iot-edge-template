#!/bin/bash

########################################################
# Variables ------------------------------------------ #
# Modify these variables before running                #
########################################################

RG_NAME="ianphil-IoT"
LOCATION="eastus"
IOT_HUB_NAME="ianphiledgetest"
ACR_NAME="ianphilacrtest"

########################################################
# Commands ------------------------------------------- #
########################################################

# Create Resource Group
echo "Creating Resource Group"
RG_STATE=$(az group create --name $RG_NAME --location $LOCATION --query properties.provisioningState -o tsv)
[[ "$RG_STATE" == "Succeeded" ]] || { echo >&2 Creating Resource Group failed; exit 1; }
echo "Completed successfully"
echo " "

# Create Azure IoT Hub
echo "Creating Azure IoT Hub"
HUB_STATE=$(az iot hub create --name $IOT_HUB_NAME --resource-group $RG_NAME --query properties.provisioningState -o tsv)
[[ "$HUB_STATE" == "Succeeded" ]] || { echo >&2 Creating Azure IoT Hub failed; exit 1; }
echo "Completed successfully"
echo " "

# Create Azure Container Registry (with admin password)
echo "Creating Azure Container Registry"
ACR_STATE=$(az acr create --name $ACR_NAME --resource-group $RG_NAME --sku Basic --admin-enabled --query provisioningState -o tsv)
[[ "$ACR_STATE" == "Succeeded" ]] || { echo >&2 Creating ACR failed; exit 1; }
echo "Completed successfully"
echo " "

# Print info about deployment
echo IoT Hub Connection: $(az iot hub show-connection-string -n $IOT_HUB_NAME --query connectionString -o tsv)
echo ACR Login Server is: $(az acr show -n $ACR_NAME -g $RG_NAME --query loginServer -o tsv)
echo ACR Password is: $(az acr credential show --name $ACR_NAME --resource-group $RG_NAME --query "passwords[0].value" -o tsv)
echo " "
