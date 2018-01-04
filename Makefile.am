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


define fpm-python =
fpm -s python -t $1 \
	-m "$(CORE_MAINTAINERS)" \
	--vendor "$(CORE_VENDOR)" \
	$2
endef

define fpm-gui =
fpm -s dir -t $1 -n core-gui \
	-m "$(CORE_MAINTAINERS)" \
	--license "BSD" \
	--description "Common Open Research Emulator GUI front-end" \
	--url http://www.nrl.navy.mil/itd/ncs/products/core \
	--vendor "$(CORE_VENDOR)" \
	-p core-gui_VERSION_ARCH.$1 \
	-v $(CORE_VERSION) \
	-d "bash" \
	-d "tcl" \
	-d "tk" \
	$2 \
	-C $(DESTDIR)
endef

.PHONY: fpm
fpm: clean-local-fpm
	$(call fpm-gui,rpm,-d "tkimg")
	$(call fpm-gui,deb,-d "libtk-img")
	$(call fpm-python,rpm,daemon/ns3/setup.py)
	$(call fpm-python,deb,daemon/ns3/setup.py)
	fpm -s python -t rpm \
		-m "$(CORE_MAINTAINERS)" \
		--vendor "$(CORE_VENDOR)" \
		-d "procps-ng" \
		-d "bash >= 3.0" \
		-d "bridge-utils" \
		-d "ebtables" \
		-d "iproute" \
		-d "libev" \
		-d "net-tools" \
		-d "python >= 2.7, python < 3.0" \
		daemon/src/setup.py daemon/setup.py
	fpm -s python -t deb \
		-m "$(CORE_MAINTAINERS)" \
		--vendor "$(CORE_VENDOR)" \
		-d "procps" \
		-d "libc6 >= 2.14" \
		-d "bash >= 3.0" \
		-d "bridge-utils" \
		-d "ebtables" \
		-d "iproute2" \
		-d "libev4" \
		-d "python (>= 2.7), python (<< 3.0)" \
		--deb-recommends quagga \
		daemon/src/setup.py daemon/setup.py

.PHONY: clean-local-fpm
clean-local-fpm:
	-rm -rf *.deb
	-rm -rf *.rpm

.PHONY: core-restart
core-restart:
	/etc/init.d/core-daemon stop
	daemon/sbin/core-cleanup
	rm -f /var/log/core-daemon.log
	/etc/init.d/core-daemon start

clean-local: clean-local-fpm

.version: Makefile
	echo $(CORE_VERSION) > $@

.version.date: Makefile
	echo $(CORE_VERSION_DATE) > $@
