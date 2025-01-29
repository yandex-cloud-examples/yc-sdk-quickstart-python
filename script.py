# Importing modules and the config.json file
import logging
import os
import json
import grpc

import yandexcloud
from yandex.cloud.compute.v1.image_service_pb2 import GetImageLatestByFamilyRequest
from yandex.cloud.compute.v1.image_service_pb2_grpc import ImageServiceStub
from yandex.cloud.compute.v1.instance_pb2 import IPV4, Instance
from yandex.cloud.compute.v1.instance_service_pb2 import (
    AttachedDiskSpec,
    CreateInstanceMetadata,
    CreateInstanceRequest,
    NetworkInterfaceSpec,
    OneToOneNatSpec,
    PrimaryAddressSpec,
    ResourcesSpec,
)
from yandex.cloud.compute.v1.instance_service_pb2_grpc import InstanceServiceStub

# Function to create a VM
def create_instance(sdk, public_ssh):
    # Loading configuration from the config.json file
    with open("config.json", "r") as file:
        config = json.load(file)

    # Preparing metadata
    metadata = {
        key: value.replace('USERNAME', config['username']).replace('SSH_PUBLIC_KEY', public_ssh)
        for key, value in config['metadata'].items()
    }

    
    # Getting the latest image by family
    image_service = sdk.client(ImageServiceStub)
    folder_family_id = config['resources']['image']['folder_family_id']
    family = config['resources']['image']['family']
    source_image = image_service.GetLatestByFamily(
        GetImageLatestByFamilyRequest(folder_id=folder_family_id, family=family)
    )

    # Creating a VM instance
    instance_service = sdk.client(InstanceServiceStub)
    operation = instance_service.Create(
        CreateInstanceRequest(
            folder_id=config['folder_id'],
            name=config['resources']['name'],
            metadata=metadata,
            resources_spec=ResourcesSpec(
                memory=config['resources']['resources_spec']['memory'],
                cores=config['resources']['resources_spec']['cores'],
            ),
            labels=config['labels'],
            zone_id=config['resources']['zone_id'],
            platform_id=config['resources']['platform_id'],
            boot_disk_spec=AttachedDiskSpec(
                auto_delete=config['resources']['boot_disk_spec']['auto_delete'],
                disk_spec=AttachedDiskSpec.DiskSpec(
                    type_id=config['resources']['boot_disk_spec']['disk_spec']['type_id'],
                    size=config['resources']['boot_disk_spec']['disk_spec']['size'],
                    image_id=source_image.id,
                ),
            ),
            network_interface_specs=[
                NetworkInterfaceSpec(
                    subnet_id=config['resources']['subnet_id'],
                    primary_v4_address_spec=PrimaryAddressSpec(
                        one_to_one_nat_spec=OneToOneNatSpec(
                            ip_version=IPV4,
                        )
                    ),
                ),
            ],
        )
    )
    
    logging.info("Creating initiated")
    return operation

# Entry point of the program
def main():
    logging.basicConfig(level=logging.INFO)
    # Extracting variables from the environment
    iam_token = os.getenv("IAM_TOKEN")
    public_ssh_path = os.getenv("SSH_PUBLIC_KEY_PATH")
    
    # Setting up the interceptor for retries
    interceptor = yandexcloud.RetryInterceptor(max_retry_count=5, retriable_codes=[grpc.StatusCode.UNAVAILABLE])
    sdk = yandexcloud.SDK(interceptor=interceptor, iam_token=iam_token)

    # Reading the public SSH key
    with open(public_ssh_path) as infile:
        public_ssh = infile.read()

    # Create the operation for creating a VM instance
    operation = create_instance(sdk, public_ssh)
    operation_result = sdk.wait_operation_and_get_result(
        operation,
        response_type=Instance,
        meta_type=CreateInstanceMetadata,
    )

if __name__ == "__main__":
    main()