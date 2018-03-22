# CORE
# (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for building netns components.
#

SETUPPY	= setup.py
SETUPPYFLAGS = -v

if WANT_DOCS
  SUBDIRS = doc
endif

SCRIPT_FILES := $(notdir $(wildcard scripts/*))
MAN_FILES := $(notdir $(wildcard ../doc/man/*.1))

LOGROTATE_DIR		= $(DESTDIR)/$(sysconfdir)/logrotate.d
LOGROTATE_FILE		= data/core-daemon.logrotate

# Python package build
noinst_SCRIPTS = build
build:
	$(PYTHON) $(SETUPPY) $(SETUPPYFLAGS) build

# Python package install
install-exec-hook:
	$(PYTHON) $(SETUPPY) $(SETUPPYFLAGS) install \
		--root=/$(DESTDIR) \
		--prefix=$(prefix) \
		--install-lib=$(pythondir) \
		--single-version-externally-managed

#install-data-local:
#	$(MKDIR_P) $(DESTDIR)$(LOGROTATE_DIR)
#	$(INSTALL_DATA) $(LOGROTATE_FILE) \
#	    $(DESTDIR)$(LOGROTATE_DIR)/`basename $(LOGROTATE_FILE) .logrotate`

#uninstall-local:
#	rm -f $(DESTDIR)$(LOGROTATE_DIR)/`basename $(LOGROTATE_FILE) .logrotate`

# Python package uninstall
#rmdir -p $(LOGROTATE_DIR) || true
uninstall-hook:
	rm -rf $(DESTDIR)/etc/core
	rm -rf $(DESTDIR)/$(datadir)/core
	rm -f $(addprefix $(DESTDIR)/$(datarootdir)/man/man1/, $(MAN_FILES))
	rm -f $(addprefix $(DESTDIR)/$(bindir)/,$(SCRIPT_FILES))
	rm -rf $(DESTDIR)/$(pythondir)/core-$(PACKAGE_VERSION)-py$(PYTHON_VERSION).egg-info
	rm -rf $(DESTDIR)/$(pythondir)/core

# Python package cleanup
clean-local:
	-rm -rf build

# because we include entire directories with EXTRA_DIST, we need to clean up
# the source control files
dist-hook:
	-rm -rf `find $(distdir)/ -name '*.pyc'`

distclean-local:
	-rm -rf core.egg-info
	

DISTCLEANFILES = Makefile.in

# files to include with distribution tarball
EXTRA_DIST = $(SETUPPY) \
	     core \
	     data \
	     doc/conf.py.in \
	     examples \
	     scripts \
	     tests \
	     test.py \
	     setup.cfg \
	     requirements.txt \
	     $(LOGROTATE_FILE)
