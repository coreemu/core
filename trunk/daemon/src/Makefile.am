# CORE
# (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for building netns.
#

AM_CFLAGS	= -Wall -fno-strict-aliasing -O3 -g @libev_CFLAGS@
# 				-DDEBUG

SRC_COMMON	= vnode_msg.c vnode_cmd.c vnode_chnl.c vnode_io.c \
		  vnode_msg.h vnode_cmd.h vnode_chnl.h vnode_io.h \
		  vnode_tlv.h myerr.h netns.h
SRC_VNODED	= vnoded_main.c vnode_server.c netns.c \
		  vnode_server.h
SRC_VCMD	= vcmd_main.c vnode_client.c \
		  vnode_client.h
SRC_NETNS	= netns_main.c netns.c netns.h

sbin_PROGRAMS	= vnoded vcmd netns
vnoded_LDADD	= @libev_LIBS@
vnoded_SOURCES	= ${SRC_COMMON} ${SRC_VNODED}
vcmd_LDADD	= @libev_LIBS@
vcmd_SOURCES	= ${SRC_COMMON} ${SRC_VCMD}
netns_SOURCES	= ${SRC_NETNS}

# this triggers automake to run setup.py for building the Python libraries
#   actual library names are netns.so and vcmd.so
#   SOURCES line prevents 'make dist' from looking for a 'libnetns.c' file
noinst_LIBRARIES = libnetns.a
libnetns_a_SOURCES = netnsmodule.c vcmdmodule.c
libnetns.a:
	SBINDIR=@SBINDIR@ LDFLAGS="$(LDFLAGS) @libev_LIBS@" CFLAGS="$(CFLAGS) @libev_CFLAGS@" $(PYTHON) setup.py build

install:	install-exec-hook

# Python libraries install
install-exec-hook:
	SBINDIR=${DESTDIR}/@SBINDIR@ $(PYTHON) setup.py install --prefix=${DESTDIR}/${prefix} --install-purelib=${DESTDIR}/${pythondir} --install-platlib=${DESTDIR}/${pyexecdir} --no-compile
#python setup.py install --prefix=${DESTDIR}${PYTHON_PREFIX}

# Python libraries uninstall
uninstall-hook:
	rm -f ${sbindir}/vnoded
	rm -f ${sbindir}/vcmd
	rm -f ${sbindir}/netns
	rm -f ${pythondir}/netns-*.egg-info
	rm -f ${pythondir}/netns.so
	rm -f ${pythondir}/vcmd.so

# Python libraries cleanup
clean-local: clean-local-check
.PHONY: clean-local-check
clean-local-check:
	-rm -rf build

rpmbuild.sh:
	echo SBINDIR=@SBINDIR@ LDFLAGS="$(LDFLAGS)" CFLAGS="$(CFLAGS) @libev_CFLAGS@" $(PYTHON) setup.py build > rpmbuild.sh
	chmod a+x rpmbuild.sh

rpm:	rpmbuild.sh
	$(PYTHON) setup.py bdist_rpm --build-script=rpmbuild.sh --requires="libev" --build-requires="libev-devel"

# extra cruft to remove
DISTCLEANFILES	= Makefile.in rpmbuild.sh MANIFEST

# include source files for Python libraries with distribution tarball
EXTRA_DIST	=  setup.py MANIFEST.in

