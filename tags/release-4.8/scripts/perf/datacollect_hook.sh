#!/bin/sh
# experiment hook script; write commands here to execute on the host at the
# specified state

sh /usr/local/share/core/examples/hooks/perflogstop.sh
sh /usr/local/share/core/examples/hooks/sessiondatacollect.sh
sh /usr/local/share/core/examples/hooks/timesyncstart.sh
