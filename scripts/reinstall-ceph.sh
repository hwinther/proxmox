systemctl restart pvestatd
rm -rf /etc/systemd/system/ceph*
killall -9 ceph-mon ceph-mgr ceph-mds
rm -rf /etc/ceph /etc/pve/ceph.conf /etc/pve/priv/ceph* /var/lib/ceph
pveceph purge
systemctl restart pvestatd
apt purge ceph-mon ceph-osd ceph-mgr ceph-mds
systemctl restart pvestatd
rm /etc/init.d/ceph
for i in $(apt search ceph | grep installed | awk -F/ '{print $1}'); do apt reinstall $i; done
dpkg-reconfigure ceph-base
dpkg-reconfigure ceph-mds
dpkg-reconfigure ceph-common
dpkg-reconfigure ceph-fuse
for i in $(apt search ceph | grep installed | awk -F/ '{print $1}'); do apt reinstall $i; done
systemctl restart pvestatd
mkdir -p /etc/ceph
mkdir -p /var/lib/ceph/bootstrap-osd
mkdir -p /var/lib/ceph/mgr
mkdir -p /var/lib/ceph/mon
pveceph install
systemctl restart pvestatd
pveceph init
systemctl restart pvestatd
