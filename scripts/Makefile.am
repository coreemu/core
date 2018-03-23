# CORE
# (c)2011-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for installing scripts.
#

CLEANFILES	= core-daemon

DISTCLEANFILES	= Makefile.in core-daemon.service core-daemon

EXTRA_DIST	= core-daemon.in core-daemon.service.in

SUBDIRS		= perf

# install startup scripts based on --with-startup=option configure option
# init.d (default), systemd
if WANT_INITD
startupdir	= /etc/init.d
startup_SCRIPTS	= core-daemon
endif
if WANT_SYSTEMD
startupdir	= /etc/systemd/system
startup_SCRIPTS	= core-daemon.service
endif

# remove extra scripts and their directories if they are empty
uninstall-hook:
	rmdir -p $(startupdir) || true
