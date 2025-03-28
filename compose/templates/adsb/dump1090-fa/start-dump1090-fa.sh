#!/command/with-contenv bash
# https://github.com/edgeofspace/dump1090-fa/blob/master/dump1090.c
# --net-ri-port <ports>    TCP raw input listen ports  (default: 30001)
# --net-ro-port <ports>    TCP raw output listen ports (default: 30002)
# --net-sbs-port <ports>   TCP BaseStation output listen ports (default: 30003)
# --net-bi-port <ports>    TCP Beast input listen ports  (default: 30004,30104)
# --net-bo-port <ports>    TCP Beast output listen ports (default: 30005)

echo Starting dump1090-fa

/usr/bin/dump1090-fa \
    --device-type $DEVICE_TYPE --device-index $DEVICE_INDEX --gain 60 --adaptive-range \
    --wisdom /etc/dump1090-fa/wisdom.local \
    --fix --lat $LAT --lon $LON --max-range 360 \
    --net-ro-port 30002 --net-sbs-port 30003 --net-bi-port 30004,30104 --net-bo-port 30005 \
    --json-location-accuracy 1 --write-json /run/dump1090-fa \
    $EXTRA_ARGS
