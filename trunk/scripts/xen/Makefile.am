# CORE
# (c)2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for installing Xen scripts.
#

install-exec-hook:
	test -d "$(DESTDIR)/etc/init.d" || \
		mkdir -p $(DESTDIR)/etc/init.d
	test -d "$(DESTDIR)/etc/xen/scripts" && \
		cp -f linux/scripts/vif-core $(DESTDIR)/etc/xen/scripts

