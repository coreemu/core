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
		  core-cleanup.1 core-manage.1
endif
man_MANS	= $(GUI_MANS) $(DAEMON_MANS)

.PHONY: generate-mans
generate-mans:
	$(HELP2MAN) --source CORE 'sh $(top_srcdir)/gui/core-gui' -o core-gui.1
	$(HELP2MAN) --no-info --source CORE $(top_srcdir)/netns/vnoded -o vnoded.1
	$(HELP2MAN) --no-info --source CORE $(top_srcdir)/netns/vcmd -o vcmd.1
	$(HELP2MAN) --no-info --source CORE $(top_srcdir)/netns/netns -o netns.1
	$(HELP2MAN) --version-string=$(PACKAGE_VERSION) --no-info --source CORE $(top_srcdir)/daemon/scripts/core-daemon -o core-daemon.1
	$(HELP2MAN) --version-string=$(PACKAGE_VERSION) --no-info --source CORE $(top_srcdir)/daemon/scripts/coresendmsg -o coresendmsg.1
	$(HELP2MAN) --version-string=$(PACKAGE_VERSION) --no-info --source CORE $(top_srcdir)/daemon/scripts/core-cleanup -o core-cleanup.1
	$(HELP2MAN) --version-string=$(PACKAGE_VERSION) --no-info --source CORE $(top_srcdir)/daemon/scripts/core-manage -o core-manage.1

.PHONY: diff
diff:
	for m in ${man_MANS}; do \
	    colordiff -u $$m $$m.new | less -R; \
	done;

clean-local:
	-rm -f $(addsuffix .new,$(GUI_MANS))
	-rm -f $(addsuffix .new,$(DAEMON_MANS))

DISTCLEANFILES	= Makefile.in
EXTRA_DIST	= $(man_MANS)
