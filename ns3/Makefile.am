# CORE
# (c)2012 the Boeing Company.
# See the LICENSE file included in this directory.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for building corens3 components.
#

SETUPPY	= setup.py
SETUPPYFLAGS = -v

#EXAMPLE_FILES := $(wildcard examples/*)
#coreexampledir = $(datadir)/core/examples/corens3
#dist_coreexample_SCRIPTS = $(EXAMPLE_FILES)

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
		--single-version-externally-managed \
		--no-compile

# Python package uninstall
uninstall-hook:
	rm -rf core_ns3.egg-info
	rm -rf $(DESTDIR)/$(pythondir)/core_ns3-$(PACKAGE_VERSION)-py$(PYTHON_VERSION).egg-info
	rm -rf $(DESTDIR)/$(pythondir)/corens3
	rm -rf $(DESTDIR)/$(datadir)/corens3

# Python package cleanup
clean-local:
	-rm -rf build

# because we include entire directories with EXTRA_DIST, we need to clean up
# the source control files
dist-hook:
	rm -rf `find $(distdir)/ -name '*.pyc'`

DISTCLEANFILES = Makefile.in *.pyc corens3/*.pyc MANIFEST

# files to include with distribution tarball
EXTRA_DIST = LICENSE $(SETUPPY) corens3
