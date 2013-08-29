# CORE
# (c)2011-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for installing scripts.
#

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
install-exec-hook:
	test -d "$(DESTDIR)/usr/local/etc/rc.d" || \
		mkdir -p $(DESTDIR)/usr/local/etc/rc.d
	test -d "$(DESTDIR)/usr/local/etc/rc.d" && \
		cp -f core-daemon-rc.d $(DESTDIR)/usr/local/etc/rc.d/core-daemon
else

if WANT_INITD
install-exec-hook:
	test -d "$(DESTDIR)/etc/init.d" || \
		mkdir -p $(DESTDIR)/etc/init.d
	test -d "$(DESTDIR)/etc/init.d" && \
		cp -f core-daemon-init.d $(DESTDIR)/etc/init.d/core-daemon
endif
if WANT_SYSTEMD
install-exec-hook:
	test -d "$(DESTDIR)/etc/systemd/system" || \
		mkdir -p $(DESTDIR)/etc/systemd/system
	test -d "$(DESTDIR)/etc/systemd/system" && \
		cp -f core-daemon.service $(DESTDIR)/etc/systemd/system/
endif
if WANT_SUSE
install-exec-hook:
	test -d "$(DESTDIR)/etc/init.d" || \
		mkdir -p $(DESTDIR)/etc/init.d
	test -d "$(DESTDIR)/etc/init.d" && \
		cp -f core-daemon-init.d-SUSE $(DESTDIR)/etc/init.d/core-daemon
endif
# endif FreeBSD
endif

# remove extra scripts and their directories if they are empty
uninstall-hook:
	rm -f /etc/init.d/core-daemon /usr/local/etc/rc.d/core-daemon
