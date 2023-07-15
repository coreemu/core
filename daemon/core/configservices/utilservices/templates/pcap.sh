#!/bin/sh
# set tcpdump options here (see 'man tcpdump' for help)
# (-s snap length, -C limit pcap file length, -n disable name resolution)
if [ "x$1" = "xstart" ]; then
% for ifname in ifnames:
    tcpdump -s 12288 -C 10 -n -w ${node.name}.${ifname}.pcap -i ${ifname} > /dev/null 2>&1 &
% endfor
elif [ "x$1" = "xstop" ]; then
    mkdir -p $SESSION_DIR/pcap
    mv *.pcap $SESSION_DIR/pcap
fi;
