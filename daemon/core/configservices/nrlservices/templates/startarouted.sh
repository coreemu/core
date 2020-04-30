#!/bin/sh
for f in "/tmp/${node.name}_smf"; do
    count=1
    until [ -e "$f" ]; do
        if [ $count -eq 10 ]; then
            echo "ERROR: nrlmsf pipe not found: $f" >&2
            exit 1
        fi
        sleep 0.1
        count=$(($count + 1))
    done
done

ip route add ${ip4_prefix} dev lo
arouted instance ${node.name}_smf tap ${node.name}_tap stability 10 2>&1 > /var/log/arouted.log &
