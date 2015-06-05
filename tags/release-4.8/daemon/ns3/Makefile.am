# CORE
# (c)2012 the Boeing Company.
# See the LICENSE file included in this directory.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for building corens3 components.
#

SETUPPY		= setup.py
SETUPPYFLAGS	= -v

EXAMPLE_FILES	=				\
	examples/ns3lte.py			\
	examples/ns3wifi.py			\
	examples/ns3wifirandomwalk.py		\
	examples/ns3wimax.py

coreexampledir		= $(datadir)/core/examples/corens3
dist_coreexample_SCRIPTS= $(EXAMPLE_FILES)

# Python package build
noinst_SCRIPTS = build
build:
	$(PYTHON) $(SETUPPY) $(SETUPPYFLAGS) build

# Python package install
install-exec-hook:
	$(PYTHON) $(SETUPPY) $(SETUPPYFLAGS) install --prefix=${DESTDIR}/${pyprefix} --install-purelib=${DESTDIR}/${pythondir} --install-platlib=${DESTDIR}/${pyexecdir} --no-compile

# Python package uninstall
uninstall-hook:
	rm -f ${pythondir}/corens3_python-${COREDPY_VERSION}-py${PYTHON_VERSION}.egg-info
	rm -rf ${pythondir}/corens3
	rmdir -p $(coreexampledir) || true

# Python package cleanup
clean-local:
	-rm -rf build

# Python RPM package
rpm:
	$(PYTHON) $(SETUPPY) $(SETUPPYFLAGS) bdist_rpm

# because we include entire directories with EXTRA_DIST, we need to clean up
# the source control files
dist-hook:
	rm -rf `find $(distdir)/ -name .svn` `find $(distdir)/ -name '*.pyc'`

DISTCLEANFILES	= Makefile.in *.pyc corens3/*.pyc MANIFEST

# files to include with distribution tarball
EXTRA_DIST	= LICENSE $(SETUPPY) corens3
