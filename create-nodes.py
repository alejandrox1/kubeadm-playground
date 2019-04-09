#!/usr/bin/env python
"""
Copy your public ssh key into the instance's metadata:

    xclip -sel c ~/.ssh/id_rsa.pu

SSH insto the instance:

    ssh -o "StrictHostKeyChecking no" ...

List all images available:

    gcloud compute images list

List machine types per zone:

    gcloud compute machine-types list | grep us-east1-b

To delete compute instances:

    gcloud compute instances delete node-0 node-1 node-2 node-3
"""
import getpass
import os
import time
from googleapiclient.discovery import build as discovery_build
from google.oauth2 import service_account


def wait_for_operation(compute, project, zone, operation):
    print("Waiting for operation to finish...")
    while True:
        result = compute.zoneOperations().get(
            project=project,
            zone=zone,
            operation=operation).execute()

        if result["status"] == "DONE":
            print("done.")
            if "error" in result:
                raise Exception(result["error"])
            return result

        time.sleep(1)


def get_ip(compute, project, zone, instance_name):
    filter_query = "name={}".format(instance_name)
    result = compute.instances().list(
        project=project, zone=zone, filter=filter_query).execute()
    return result["items"][0]["networkInterfaces"][0]["accessConfigs"][0]["natIP"]


def delete_instance(compute, project, zone, name):
    return compute.instances().delete(
        project=project,
        zone=zone,
        instance=name).execute()


def create_instance(compute, project, zone, name):
    # Get the latest image.
    # gcloud compute images list
    image_response = compute.images().getFromFamily(
        project="ubuntu-os-cloud", family="ubuntu-1604-lts").execute()
    source_disk_image = image_response["selfLink"]

    # Configure the machine
    machine_type = "n1-standard-2"
    machine_type = "zones/{}/machineTypes/{}".format(zone, machine_type)

    config = {
        "name": name,
        "machineType": machine_type,

        # Specify the boot disk and the image to use as a source.
        "disks": [
            {
                "boot": True,
                "autoDelete": True,
                "initializeParams": {
                    "sourceImage": source_disk_image,
                }
            }
        ],

        # Specify a network interface with NAT to access the public
        # internet.
        "networkInterfaces": [{
            "network": "global/networks/default",
            "accessConfigs": [
                {"type": "ONE_TO_ONE_NAT", "name": "External NAT"}
            ]
        }],

        # Allow the instance to access cloud storage and logging.
        "serviceAccounts": [{
            "email": "default",
            "scopes": [
                "https://www.googleapis.com/auth/devstorage.read_write",
                "https://www.googleapis.com/auth/logging.write",
            ]
        }],
    }

    return compute.instances().insert(
        project=project,
        zone=zone,
        body=config).execute()


if __name__ == "__main__":
    project = "k8s-istio-218403"
    zone    = "us-east1-b"
    nodes   = 4

    # Authenticate with the googles.
    credentials = service_account.Credentials.from_service_account_file(
        "creds/serviceaccount.json")
    compute = discovery_build("compute", "v1", credentials=credentials)

    instances = []
    for i in range(nodes):
        instance_name = "node-" + str(i)
        
        print("Creating instance {}...".format(instance_name))
        operation = create_instance(compute, project, zone, instance_name)
        wait_for_operation(compute, project, zone, operation["name"])

        ip = get_ip(compute, project, zone, instance_name)
        instances.append({"name": instance_name, "ip": ip})

    for instance in instances:
        print(instance)

    with open("hosts", "w") as f:
        f.write("[masters]\n")
        f.write("master ansible_host={} ansible_user={}\n".format(
            instances[0]["ip"], getpass.getuser()))
        f.write("\n")

        f.write("[workers]\n")
        for instance in instances[1:]:
            f.write("{} ansible_host={} ansible_user={}\n".format(
                instance["name"], instance["ip"], getpass.getuser()))
