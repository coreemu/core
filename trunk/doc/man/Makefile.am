# CORE
# (c)2012-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for building man pages.
#

if WANT_GUI
  GUI_MANS 	= core-gui.1
endif
if WANT_DAEMON
  DAEMON_MANS	= vnoded.1 vcmd.1 netns.1 core-daemon.1 coresendmsg.1 \
		  core-cleanup.1 core-xen-cleanup.1 core-manage.1
endif
man_MANS	= $(GUI_MANS) $(DAEMON_MANS)

.PHONY: generate-mans
generate-mans:
	$(HELP2MAN) --source CORE 'sh $(top_srcdir)/gui/core-gui' -o core-gui.1.new
	$(HELP2MAN) --no-info --source CORE $(top_srcdir)/daemon/src/vnoded -o vnoded.1.new
	$(HELP2MAN) --no-info --source CORE $(top_srcdir)/daemon/src/vcmd -o vcmd.1.new
	$(HELP2MAN) --no-info --source CORE $(top_srcdir)/daemon/src/netns -o netns.1.new
	$(HELP2MAN) --version-string=$(CORE_VERSION) --no-info --source CORE $(top_srcdir)/daemon/sbin/core-daemon -o core-daemon.1.new
	$(HELP2MAN) --version-string=$(CORE_VERSION) --no-info --source CORE $(top_srcdir)/daemon/sbin/coresendmsg -o coresendmsg.1.new
	$(HELP2MAN) --version-string=$(CORE_VERSION) --no-info --source CORE $(top_srcdir)/daemon/sbin/core-cleanup -o core-cleanup.1.new
	$(HELP2MAN) --version-string=$(CORE_VERSION) --no-info --source CORE $(top_srcdir)/daemon/sbin/core-xen-cleanup -o core-xen-cleanup.1.new
	$(HELP2MAN) --version-string=$(CORE_VERSION) --no-info --source CORE $(top_srcdir)/daemon/sbin/core-manage -o core-manage.1.new

.PHONY: diff
diff:
	for m in ${man_MANS}; do \
	    colordiff -u $$m $$m.new | less -R; \
	done;

DISTCLEANFILES	= Makefile.in
EXTRA_DIST	= $(man_MANS)
