#!/bin/bash
# Creates a Ubuntu Cloud-Init Ready VM Template in Proxmox
#
# Update the image name and URL for Ubuntu 22.04 LTS

export IMAGENAME="jammy-server-cloudimg-amd64.img"
export IMAGEURL="https://cloud-images.ubuntu.com/jammy/current/"
export STORAGE="local-zfs-cache"
export VMNAME="ubuntu-2204-cloudinit-template"
export VMID=902204
export VMMEM=2048
export VMSETTINGS="--net0 virtio,bridge=vmbr0"

wget -O ${IMAGENAME} --continue ${IMAGEURL}/${IMAGENAME} && 
qm create ${VMID} --name ${VMNAME} --memory ${VMMEM} ${VMSETTINGS} && 
qm importdisk ${VMID} ${IMAGENAME} ${STORAGE} &&
qm set ${VMID} --scsihw virtio-scsi-pci --scsi0 ${STORAGE}:vm-${VMID}-disk-0 &&
qm set ${VMID} --ide2 ${STORAGE}:cloudinit &&
qm set ${VMID} --boot c --bootdisk scsi0 &&
qm set ${VMID} --serial0 socket --vga serial0 &&
qm template ${VMID} &&
echo "TEMPLATE ${VMNAME} successfully created!" && 
echo "Now create a clone of VM with ID ${VMID} in the Webinterface.."
