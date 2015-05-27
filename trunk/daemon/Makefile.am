# CORE
# (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for building netns components.
#

SETUPPY		= setup.py
SETUPPYFLAGS	= -v

if WANT_NETNS
  SUBDIRS 	= src ns3
endif

SBIN_FILES		=			\
	sbin/core-cleanup			\
	sbin/core-daemon			\
	sbin/core-manage			\
	sbin/core-xen-cleanup			\
	sbin/coresendmsg

dist_sbin_SCRIPTS	= $(SBIN_FILES)

CONF_FILES		=			\
	data/core.conf				\
	data/xen.conf

coreconfdir		= $(CORE_CONF_DIR)
dist_coreconf_DATA	= $(CONF_FILES)

EXAMPLE_FILES		=			\
	examples/controlnet_updown		\
	examples/emanemodel2core.py		\
	examples/findcore.py			\
	examples/stopsession.py

coreexdir		= $(datadir)/core/examples
dist_coreex_SCRIPTS	= $(EXAMPLE_FILES)

EXAMPLE_MYSERVICES_FILES =			\
	examples/myservices/README.txt		\
	examples/myservices/__init__.py		\
	examples/myservices/sample.py

coreexmyservicesdir	= $(coreexdir)/myservices
dist_coreexmyservices_DATA = $(EXAMPLE_MYSERVICES_FILES)

EXAMPLE_NETNS_FILES	=				\
	examples/netns/basicrange.py			\
	examples/netns/distributed.py			\
	examples/netns/emane80211.py			\
	examples/netns/howmanynodes.py			\
	examples/netns/iperf-performance-chain.py	\
	examples/netns/iperf-performance.sh		\
	examples/netns/ospfmanetmdrtest.py		\
	examples/netns/switch.py			\
	examples/netns/switchtest.py			\
	examples/netns/twonodes.sh			\
	examples/netns/wlanemanetests.py		\
	examples/netns/wlantest.py

coreexnetnsdir		= $(coreexdir)/netns
dist_coreexnetns_SCRIPTS= $(EXAMPLE_NETNS_FILES)

EXAMPLE_SERVICES_FILES	=			\
	examples/services/sampleFirewall	\
	examples/services/sampleIPsec		\
	examples/services/sampleVPNClient	\
	examples/services/sampleVPNServer

coreexservicesdir	= $(coreexdir)/services
dist_coreexservices_DATA= $(EXAMPLE_SERVICES_FILES)

# Python package build
noinst_SCRIPTS = build
build:
	$(PYTHON) $(SETUPPY) $(SETUPPYFLAGS) build

# Python package install
install-exec-hook:
	$(PYTHON) $(SETUPPY) $(SETUPPYFLAGS) install --prefix=${DESTDIR}/${pyprefix} --install-purelib=${DESTDIR}/${pythondir} --install-platlib=${DESTDIR}/${pyexecdir} --no-compile

# Python package uninstall
uninstall-hook:
	rm -f ${pythondir}/core_python-${COREDPY_VERSION}-py${PYTHON_VERSION}.egg-info
	rm -f ${pythondir}/core_python_netns-1.0-py${PYTHON_VERSION}.egg-info
	rm -rf ${pythondir}/core
	rmdir -p $(coreexservicesdir) || true
	rmdir -p $(coreexnetnsdir) || true
	rmdir -p $(coreexmyservicesdir) || true
	rmdir -p $(coreexdir) || true
	rmdir -p $(coreconfdir) || true

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

DISTCLEANFILES	= Makefile.in core/*.pyc MANIFEST doc/Makefile.in doc/Makefile \
		  doc/conf.py core/addons/*.pyc

# files to include with distribution tarball
EXTRA_DIST	= $(SETUPPY) MANIFEST.in CORE.e4p core doc
