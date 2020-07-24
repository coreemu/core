# CORE
# (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for building netns components.
#

if WANT_DOCS
DOCS = doc
endif

SUBDIRS = proto $(DOCS)

# because we include entire directories with EXTRA_DIST, we need to clean up
# the source control files
dist-hook:
	-rm -rf `find $(distdir)/ -name '*.pyc'`

distclean-local:
	-rm -rf core.egg-info

DISTCLEANFILES = Makefile.in

# files to include with distribution tarball
EXTRA_DIST = core \
	     data \
	     doc/conf.py.in \
	     examples \
	     scripts \
	     tests \
	     setup.cfg \
	     poetry.lock \
	     pyproject.toml
