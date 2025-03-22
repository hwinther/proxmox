#!/command/with-contenv bash
# mkdir -p /usr/local/share/adsbexchange && 
echo "$ADSBX_UUID" > /usr/local/share/adsbexchange/adsbx-uuid

cat <<EOF > /etc/default/adsbexchange
INPUT="$RECEIVER_HOST:$RECEIVER_PORT"
REDUCE_INTERVAL="0.5"

# feed name for checking MLAT sync (adsbx.org/sync)
# also displayed on the MLAT map: map.adsbexchange.com/mlat-map
USER="0"

LATITUDE="$LAT"
LONGITUDE="$LON"

ALTITUDE="0"

# this is the source for 978 data, use port 30978 from dump978 --raw-port
# if you're not receiving 978, don't worry about it, not doing any harm!
UAT_INPUT="127.0.0.1:30978"

RESULTS="--results beast,connect,$MLAT_BEAST_HOST:$MLAT_BEAST_PORT"
RESULTS2="--results basestation,listen,31003"
RESULTS3="--results beast,listen,30157"
RESULTS4="--results beast,connect,127.0.0.1:30154"
# add --privacy between the quotes below to disable having the feed name shown on the mlat map
# (position is never shown accurately no matter the settings)
PRIVACY=""
INPUT_TYPE="dump1090"

MLATSERVER="feed.adsbexchange.com:31090"
TARGET="--net-connector feed1.adsbexchange.com,30004,beast_reduce_out,feed2.adsbexchange.com,64004"
NET_OPTIONS="--net-heartbeat 60 --net-ro-size 1280 --net-ro-interval 0.2 --net-ro-port 0 --net-sbs-port 0 --net-bi-port 30154 --net-bo-port 0 --net-ri-port 0 --write-json-every 1"
JSON_OPTIONS="--max-range 450 --json-location-accuracy 2 --range-outline-hours 24"
EOF

echo Starting adsbexchange
/usr/local/share/adsbexchange/adsbexchange-feed.sh
