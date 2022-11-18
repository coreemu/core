# CORE
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
	     doc/conf.py.in \
	     tests \
	     setup.cfg \
	     poetry.lock \
	     pyproject.toml
