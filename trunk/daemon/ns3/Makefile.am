# CORE
# (c)2012 the Boeing Company.
# See the LICENSE file included in this directory.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for building corens3 components.
#

# Python package build
noinst_SCRIPTS = build
build:
	$(PYTHON) setup.py build

# Python package install
install-exec-hook:
	CORE_CONF_DIR=${DESTDIR}/${CORE_CONF_DIR} $(PYTHON) setup.py install --prefix=${DESTDIR}/${prefix} --install-purelib=${DESTDIR}/${pythondir} --install-platlib=${DESTDIR}/${pyexecdir} --no-compile

# Python package uninstall
uninstall-hook:
	rm -f ${pythondir}/corens3_python-${COREDPY_VERSION}-py${PYTHON_VERSION}.egg-info
	rm -rf ${pythondir}/corens3

# Python package cleanup
clean-local:
	-rm -rf build

# Python RPM package
rpm:
	$(PYTHON) setup.py bdist_rpm

# because we include entire directories with EXTRA_DIST, we need to clean up
# the source control files
dist-hook:
	rm -rf `find $(distdir)/ -name .svn` `find $(distdir)/ -name '*.pyc'`

DISTCLEANFILES	= Makefile.in *.pyc corens3/*.pyc MANIFEST

# files to include with distribution tarball
EXTRA_DIST	= LICENSE setup.py corens3 examples
