FROM debian:bullseye

RUN apt update && apt install wget -y
RUN echo "deb [arch=amd64] http://download.proxmox.com/debian/pve bullseye pve-no-subscription" > /etc/apt/sources.list.d/pve-install-repo.list
RUN wget https://enterprise.proxmox.com/debian/proxmox-release-bullseye.gpg -O /etc/apt/trusted.gpg.d/proxmox-release-bullseye.gpg
RUN apt update -y
RUN DEBIAN_FRONTEND=noninteractive apt -o Dpkg::Options::="--force-confold" -o Dpkg::Options::="--force-confdef" full-upgrade -q -y --allow-downgrades --allow-remove-essential --allow-change-held-packages
RUN apt install -y pve-kernel-6.2

# FROM baseimage
RUN DEBIAN_FRONTEND=noninteractive apt -o Dpkg::Options::="--force-confold" -o Dpkg::Options::="--force-confdef" install -y proxmox-ve postfix open-iscsi
