#!/bin/bash
# Creates a Debian 12 Cloud-Init Ready VM Template in Proxmox

#export IMAGENAME="debian-12-genericcloud-arm64.qcow2"
#export IMAGEURL="https://cdimage.debian.org/images/cloud/bookworm/latest/"

#export IMAGENAME="debian-12-generic-arm64.raw"
#export IMAGEURL="https://cdimage.debian.org/images/cloud/bookworm/latest/"

#export IMAGENAME="ubuntu-22.04-server-cloudimg-amd64.img"
#export IMAGEURL="https://cloud-images.ubuntu.com/releases/22.04/release/"
#export IMAGENAME="ubuntu-24.04-server-cloudimg-amd64.img"
#export IMAGEURL="https://cloud-images.ubuntu.com/releases/24.04/release/"
export IMAGENAME="ubuntu-24.04-minimal-cloudimg-amd64.img"
export IMAGEURL="https://cloud-images.ubuntu.com/minimal/releases/noble/release/"

#export IMAGENAME="debian-10-openstack-amd64.qcow2"
#export IMAGEURL="https://cloud.debian.org/cdimage/cloud/OpenStack/current-10/"

export IMAGEFOLDER=/tmp
export STORAGE="local"
export VMNAME="debian-12-cloudinit-template"
export VMID=10001
export VMMEM=2048
export VMCORES=4
export VMSETTINGS="--net0 virtio,bridge=vmbr0,tag=2001"
export DISK_RESIZE=2G

USER_YAML="/var/lib/vz/snippets/cloud-init-debian-user.yaml"
VENDOR_YAML="/var/lib/vz/snippets/cloud-init-debian-docker.yaml"
#NETWORK_YAML="/var/lib/vz/snippets/cloud-init-network.yaml"

wget -O ${IMAGEFOLDER}/${IMAGENAME} --continue ${IMAGEURL}/${IMAGENAME} &&
qm create ${VMID} --name ${VMNAME} --memory ${VMMEM} --cores ${VMCORES} --cpu host --ostype l26 ${VMSETTINGS} &&
qm set ${VMID} --scsi0 ${STORAGE}:0,import-from=${IMAGEFOLDER}/${IMAGENAME},discard=on &&
qm resize ${VMID} scsi0 +${DISK_RESIZE} &&
qm set ${VMID} --scsi2 ${STORAGE}:cloudinit &&
qm set ${VMID} --boot='order=scsi0;scsi2' --scsihw virtio-scsi-single &&
qm set ${VMID} --serial0 socket --vga serial0 &&
qm set ${VMID} --agent enabled=1,fstrim_cloned_disks=1

CICUSTOM_PARTS=()

if [ -n "$USER_YAML" ]; then
    if [ -L "$USER_YAML" ] && [ -e "$USER_YAML" ]; then
        echo "Symlink for cloud-init-debian-user.yaml exists."
    else
        echo "Symlink for cloud-init-debian-user.yaml does not exist."
        ln -s $PWD/cloud-init-debian-user.yaml $USER_YAML
    fi
    CICUSTOM_PARTS+=("user=local:snippets/cloud-init-debian-user.yaml")
else
    echo "No user cloud-init file specified."
    #qm set ${VMID} --ciuser user &&
    #qm set ${VMID} --cipassword temp &&
    qm set ${VMID} --sshkeys ./ci-ssh-keys &&
    qm set ${VMID} --ciupgrade 1
fi

if [ -n "$VENDOR_YAML" ]; then
    if [ -L "$VENDOR_YAML" ] && [ -e "$VENDOR_YAML" ]; then
        echo "Symlink for cloud-init-debian-docker.yaml exists."
    else
        echo "Symlink for cloud-init-debian-docker.yaml does not exist."
        ln -s $PWD/cloud-init-debian-docker.yaml $VENDOR_YAML
    fi
    CICUSTOM_PARTS+=("vendor=local:snippets/cloud-init-debian-docker.yaml")
else
    echo "No vendor cloud-init file specified."
fi

if [ -n "$NETWORK_YAML" ]; then
    if [ -L "$NETWORK_YAML" ] && [ -e "$NETWORK_YAML" ]; then
        echo "Symlink for cloud-init-network.yaml exists."
    else
        echo "Symlink for cloud-init-network.yaml does not exist."
        ln -s $PWD/cloud-init-network.yaml $NETWORK_YAML
    fi
    CICUSTOM_PARTS+=("network=local:snippets/cloud-init-network.yaml")
else
    echo "No network cloud-init file specified, defaulting to DHCP and SLAAC."
    qm set ${VMID} --ipconfig0 ip=dhcp,ip6=auto
fi

CICUSTOM=$(IFS=,; echo "${CICUSTOM_PARTS[*]}")

qm set ${VMID} --cicustom "${CICUSTOM}"
#qm set ${VMID} --cicustom "user=local:snippets/cloud-init-debian-user.yaml,vendor=local:snippets/cloud-init-debian-docker.yaml" &&
#qm set ${VMID} --cicustom "vendor=local:snippets/cloud-init-debian-docker.yaml" &&

qm template ${VMID} &&
echo "TEMPLATE ${VMNAME} successfully created!" &&
echo "Now create a clone of VM with ID ${VMID} in the Webinterface.."
