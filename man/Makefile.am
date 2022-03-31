# CORE

if WANT_DAEMON
  DAEMON_MANS	= vnoded.1 vcmd.1 netns.1 core-daemon.1 core-gui.1 \
		  core-cleanup.1
endif
man_MANS	= $(DAEMON_MANS)

.PHONY: generate-mans
generate-mans:
	$(HELP2MAN) --source CORE 'sh $(top_srcdir)/gui/core-gui' -o core-gui.1
	$(HELP2MAN) --no-info --source CORE $(top_srcdir)/netns/vnoded -o vnoded.1
	$(HELP2MAN) --no-info --source CORE $(top_srcdir)/netns/vcmd -o vcmd.1
	$(HELP2MAN) --no-info --source CORE $(top_srcdir)/netns/netns -o netns.1
	$(HELP2MAN) --version-string=$(PACKAGE_VERSION) --no-info --source CORE $(top_srcdir)/daemon/scripts/core-daemon -o core-daemon.1
	$(HELP2MAN) --version-string=$(PACKAGE_VERSION) --no-info --source CORE $(top_srcdir)/daemon/scripts/core-cleanup -o core-cleanup.1

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
