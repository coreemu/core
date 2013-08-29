#!/bin/sh
#

# PROVIDE: core
# REQUIRE: NETWORKING

# To enable CORE services on startup, add the following line to /etc/rc.conf:
# core_enable="YES"
#

. /etc/rc.subr

name="core"
rcvar=`set_rcvar`

stop_postcmd=stop_postcmd

stop_postcmd()
{
  rm -f $pidfile
}

# defaults
load_rc_config $name
: ${core_enable="NO"}
: ${core_flags="-d"}
: ${core_daemons="core-daemon"}

core_cmd=$1

case "${core_cmd}" in
    start)
        ;;
    stop|restart)
        core_daemons=$(reverse_list ${core_daemons})
        ;;
esac

for daemon in ${core_daemons}; do
    command=/usr/local/sbin/${daemon}
    pidname=`echo ${daemon} | sed 's/\.//g'`
    pidfile=/var/run/${pidname}.pid
    command_interpreter=python
    if [ "${daemon}" = "core-daemon" ]; then
	command_interpreter=python
    fi
    run_rc_command "$1"
    _rc_restart_done=false
done

