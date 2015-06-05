# CORE
# (c)2011-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for installing scripts.
#

CLEANFILES	= core-daemon

DISTCLEANFILES	= Makefile.in xen/Makefile xen/Makefile.in

EXTRA_DIST	= core-daemon-init.d \
		  core-daemon.service \
		  core-daemon-rc.d \
		  core-daemon-init.d-SUSE \
		  xen

SUBDIRS		= perf

# clean up dirs included by EXTRA_DIST
dist-hook:
	rm -rf $(distdir)/xen/.svn

# install startup scripts based on --with-startup=option configure option
# FreeBSD, init.d (default), systemd, SUSE
if WANT_BSD
startupdir	= /usr/local/etc/rc.d
startup_SCRIPTS	= core-daemon

core-daemon: core-daemon-rc.d
	cp $< $@
else

if WANT_INITD
startupdir	= /etc/init.d
startup_SCRIPTS	= core-daemon

core-daemon: core-daemon-init.d
	cp $< $@
endif
if WANT_SYSTEMD
startupdir	= /etc/systemd/system
startup_SCRIPTS	= core-daemon.service
endif
if WANT_SUSE
startupdir	= /etc/init.d
startup_SCRIPTS	= core-daemon

core-daemon: core-daemon-init.d-SUSE
	cp $< $@
endif
# endif FreeBSD
endif

# remove extra scripts and their directories if they are empty
uninstall-hook:
	rmdir -p $(startupdir) || true
