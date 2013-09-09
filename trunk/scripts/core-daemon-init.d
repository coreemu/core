#!/bin/sh
### BEGIN INIT INFO
# Provides:          core-daemon
# Required-Start:    $network $remote_fs
# Required-Stop:     $network $remote_fs
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Start the core-daemon CORE daemon at boot time
# Description:       Starts and stops the core-daemon CORE daemon used to
#                    provide network emulation services for the CORE GUI
#                    or scripts.
### END INIT INFO
#
# chkconfig: 35 90 03
# description: Starts and stops the CORE daemon \
#	       used to provide network emulation services.
#
# pidfile: /var/run/core-daemon.pid
# config:  /usr/local/etc/core/

DEB=no
# Source function library.
if [ -f /etc/init.d/functions ] ; then
  . /etc/init.d/functions
elif [ -f /etc/rc.d/init.d/functions ] ; then
  . /etc/rc.d/init.d/functions
elif [ -f /lib/lsb/init-functions ] ; then
  . /lib/lsb/init-functions
  DEB=yes
else
  exit 1
fi

# search for core-daemon which may or may not be installed
cored=
for p in /usr/local/sbin \
         /usr/sbin \
         /sbin \
         /usr/local/bin \
         /usr/bin \
         /bin
do
  if [ -e $p/core-daemon ] ; then
    cored=$p/core-daemon
    break
  fi
done

# this function comes from /etc/profile
pathmunge () {
    if ! echo $PATH | /bin/egrep -q "(^|:)$1($|:)" ; then
       if [ "$2" = "after" ] ; then
          PATH=$PATH:$1
       else
          PATH=$1:$PATH
       fi
    fi
}

# these lines add to the PATH variable used by CORE and its containers
# you can add your own pathmunge statements to change the container's PATH
pathmunge "/usr/local/sbin"
pathmunge "/usr/local/bin"

RETVAL=0
PIDFILE=/var/run/core-daemon.pid

# the /etc/init.d/functions (RedHat) differs from
#     /usr/lib/init-functions (Debian)
if [ $DEB = yes ]; then
  daemon="start-stop-daemon --start -p ${PIDFILE} --exec /usr/bin/python --"
  #daemon=start_daemon
  status=status_of_proc
  msg () {
    log_daemon_msg "$@"
  }
  endmsg () {
    echo ""
  }
else
  daemon="daemon /usr/bin/python"
  status=status
  msg () {
    echo -n $"$@"
  }
  endmsg () {
    echo ""
  }
fi


start() {
	msg "Starting core-daemon"
	$daemon $cored -d
	RETVAL=$?
	endmsg
	return $RETVAL
}	

stop() {
	msg "Shutting down core-daemon"
	killproc -p ${PIDFILE} $cored
	RETVAL=$?
	rm -f ${PIDFILE}
	endmsg
	return $RETVAL
}	

restart() {
	stop
	start
}	

corestatus() {
	$status -p ${PIDFILE} core-daemon core-daemon
	return $?
}	


case "$1" in
  start)
  	start
	;;
  stop)
  	stop
	;;
  restart)
  	restart
	;;
  force-reload)
        restart
        ;;
  status)
  	corestatus
	;;
  *)
	msg "Usage: $0 {start|stop|restart|status}"
	endmsg
	exit 2
esac

exit $?
