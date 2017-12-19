# CORE
# (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Top-level Makefile for CORE project.
#

if WANT_DOCS
  DOCS			= doc daemon/doc
endif
if WANT_GUI
  GUI			= gui
endif
if WANT_DAEMON
  DAEMON		= scripts daemon
endif

# keep docs last due to dependencies on binaries
SUBDIRS			= ${GUI} ${DAEMON} ${DOCS}

ACLOCAL_AMFLAGS 	= -I config

# extra files to include with distribution tarball
EXTRA_DIST		= bootstrap.sh LICENSE \
 			  README.rst ASSIGNMENT_OF_COPYRIGHT.pdf \
			  README-Xen Changelog kernel \
			  python-prefix.py revision.sh \
			  .version .version.date \
			  packaging/bsd \
			  packaging/deb/compat \
			  packaging/deb/copyright \
			  packaging/deb/changelog \
			  packaging/deb/rules \
			  packaging/deb/control \
			  packaging/deb/core-daemon.install.in \
			  packaging/deb/core-daemon.prerm.in \
			  packaging/deb/core-gui.install.in \
			  packaging/rpm/core.spec.in \
			  packaging/rpm/specfiles.sh

DISTCLEAN_TARGETS	= aclocal.m4 config.h.in

# extra cruft to remove
DISTCLEANFILES	= aclocal.m4 config.h.in configure Makefile.in config/compile

MAINTAINERCLEANFILES =				\
	.version				\
	.version.date

# don't include svn dirs in source tarball
dist-hook:
	rm -rf `find $(distdir)/kernel -name .svn`
	rm -rf $(distdir)/packaging/bsd/.svn

# build a source RPM
.PHONY: rpm
rpm: dist
	mkdir -p $(HOME)/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
	echo '%_topdir $(HOME)/rpmbuild' > ~/.rpmmacros
	cp -afv core-@CORE_VERSION@.tar.gz ~/rpmbuild/SOURCES
	cp -afv packaging/rpm/core.spec ~/rpmbuild/SPECS
	rpmbuild -bs ~/rpmbuild/SPECS/core.spec

# build a Ubuntu deb package using CDBS
.PHONY: deb
deb:
	rm -rf debian
	mkdir -p debian
	cp -vf packaging/deb/* debian/
	@echo "First create source archive with:  dpkg-source -b core-@CORE_VERSION@"
	@echo "Then build with:  pbuilder-dist precise i386 build core*.dsc"

.PHONE: fpm
fpm:
	fpm -s python -t rpm \
			-m "CORE Developers <core-dev@nrl.navy.mil>" \
			--vendor "CORE Developers" \
			daemon/setup.py
	fpm -s python -t rpm \
    		-m "CORE Developers <core-dev@nrl.navy.mil>" \
    		--vendor "CORE Developers" \
    		daemon/src/setup.py
    fpm -s python -t rpm \
    		-m "CORE Developers <core-dev@nrl.navy.mil>" \
    		--vendor "CORE Developers" \
    		daemon/ns3/setup.py

.PHONY: fpm-deb
fpm-deb:
	fpm -s dir -t deb -n core -v $(CORE_VERSION) -C "$DESTDIR" \
			-p core_VERSION_ARCH.deb \
			--license "BSD 2-clause" \
			--vendor "CORE Developers" \
			--description "Emulate virtual networks in a box." \
			--url http://www.nrl.navy.mil/itd/ncs/products/core \
			-m "CORE Developers <core-dev@nrl.navy.mil>" \
			-d "procps" \
			-d "libc6 >= 2.14" \
			-d "bash >= 3.0" \
			-d "bridge-utils" \
			-d "ebtables" \
			-d "iproute2" \
			-d "libev4" \
			-d "python >= 2.7" \
			--deb-recommends quagga


.PHONY: fpm-rpm
fpm-rpm:
	fpm -s dir -t rpm -n core -v $(CORE_VERSION) -C "$DESTDIR" \
			-p core_VERSION_ARCH.rpm \
			--license "BSD 2-clause" \
			--vendor "CORE Developers" \
			--description "Emulate virtual networks in a box." \
			--url http://www.nrl.navy.mil/itd/ncs/products/core \
			-m "CORE Developers <core-dev@nrl.navy.mil>" \
			-d "procps" \
			-d "bash >= 3.0" \
			-d "bridge-utils" \
			-d "ebtables" \
			-d "iproute" \
			-d "libev" \
			-d "python >= 2.7"

.PHONY: core-restart
core-restart:
	/etc/init.d/core-daemon stop
	daemon/sbin/core-cleanup
	rm -f /var/log/core-daemon.log
	/etc/init.d/core-daemon start

.version: Makefile
	echo $(CORE_VERSION) > $@

.version.date: Makefile
	echo $(CORE_VERSION_DATE) > $@
