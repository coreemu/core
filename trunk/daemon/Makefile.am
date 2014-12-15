# CORE
# (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for building netns components.
#

if WANT_NETNS
  SUBDIRS 	= src ns3
endif

# Python package build
noinst_SCRIPTS = build
build:
	$(PYTHON) setup.py build

# Python package install
install-exec-hook:
	CORE_CONF_DIR=${DESTDIR}/${CORE_CONF_DIR} $(PYTHON) setup.py install --prefix=${DESTDIR}/${prefix} --install-purelib=${DESTDIR}/${pythondir} --install-platlib=${DESTDIR}/${pyexecdir} --no-compile

# Python package uninstall
uninstall-hook:
	rm -f ${SBINDIR}/core-daemon
	rm -f ${SBINDIR}/coresendmsg
	rm -f ${SBINDIR}/core-cleanup
	rm -f ${SBINDIR}/core-xen-cleanup
	rm -f ${pythondir}/core_python-${COREDPY_VERSION}-py${PYTHON_VERSION}.egg-info
	rm -f ${pythondir}/core_python_netns-1.0-py${PYTHON_VERSION}.egg-info
	rm -rf ${pythondir}/core
	rm -rf ${prefix}/share/core

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

DISTCLEANFILES	= Makefile.in core/*.pyc MANIFEST doc/Makefile.in doc/Makefile \
		  doc/conf.py core/addons/*.pyc

# files to include with distribution tarball
EXTRA_DIST	= setup.py MANIFEST.in CORE.e4p core data examples sbin doc
