#!/bin/bash
export PBS_REPOSITORY='hwinther@pbs!sync@pbs.oh.wsh.no:hwinther'
# Set export password in .bashrc:
# export PBS_PASSWORD='c24a9409-dead-beef'

export PROXMOX_OUTPUT_NO_BORDER='.'
export PROXMOX_OUTPUT_NO_HEADER='.'

DEBUG=0

function _debug {
        [ $DEBUG == "1" ] || return
        echo "[$(date +%Y%m%d-%H%M%S)] ($0): $*"
}

function _error {
        echo "[$(date +%Y%m%d-%H%M%S)] ($0) ERROR: $*" 1>&2
}

function _exit {
        ec=0
        if [ "z$1" != "z" ]; then
                ec=$1
                shift
        fi
        if [ "z$1" != "z" ]; then
                _error $*
        fi
        exit ${ec}
}

while read snapshot; do
        if [ "z${snapshot}" == "z" ]; then continue; fi
        note=$(proxmox-backup-client snapshot notes show ${snapshot})
        if [ "z${note}" == "z" ]; then
                name=""
                if [[ $snapshot == "vm/"* ]]; then
                        name=$(proxmox-backup-client restore ${snapshot} qemu-server.conf - | awk '/^name: / {print $2}')
                elif [[ $snapshot == "ct/"* ]]; then
                        name=$(proxmox-backup-client restore ${snapshot} pct.conf - | awk '/^hostname: / {print $2}')
                elif [[ $snapshot == "host/"* ]]; then
                        name=$(echo ${snapshot} | awk '{split($0,a,"/")}; {print a[2]}')
                fi

                if [ "z${name}" == "z" ]; then
                        _exit 1 "Unable to get name for snapshot ${snapshot}"
                fi

                _debug "Updating snapshot '${snapshot}' note: ${name}"
                proxmox-backup-client snapshot notes update ${snapshot} ${name}
        else
                _debug "Note already exists for snapshot '${snapshot}'"
        fi
done < <(proxmox-backup-client snapshot list | awk '{print $1}')
