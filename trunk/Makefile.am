# CORE
# (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Top-level Makefile for CORE project.
#

if WANT_DOCS
  DOCS			= doc
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
EXTRA_DIST		= bootstrap.sh LICENSE README-Xen Changelog kernel \
			  packaging/bsd \
			  packaging/deb/compat \
			  packaging/deb/copyright \
			  packaging/deb/changelog \
			  packaging/deb/core.postrm \
			  packaging/deb/rules \
			  packaging/deb/control \
			  packaging/deb/core-daemon.install.in \
			  packaging/deb/core-gui.install.in \
			  packaging/rpm/core.spec.in \
			  packaging/rpm/specfiles.sh

DISTCLEAN_TARGETS	= aclocal.m4 config.h.in

# extra cruft to remove
DISTCLEANFILES	= aclocal.m4 config.h.in configure Makefile.in config/compile

# don't include svn dirs in source tarball
dist-hook:
	rm -rf `find $(distdir)/kernel -name .svn`
	rm -rf $(distdir)/packaging/bsd/.svn

# build a source RPM using Fedora ~/rpmbuild dirs
.PHONY: rpm
rpm:
	rpmdev-setuptree
	cp -afv core-*.tar.gz ~/rpmbuild/SOURCES
	cp -afv packaging/rpm/core.spec ~/rpmbuild/SPECS
	rpmbuild -bs ~/rpmbuild/SPECS/core.spec

# build a Ubuntu deb package using CDBS
.PHONY: deb
deb:
	rm -rf debian
	mkdir -p debian
	cp -vf packaging/deb/* debian/
	@echo "First create source archive with:  dpkg-source -b core-4.5"
	@echo "Then build with:  pbuilder-dist precise i386 build core*.dsc"

.PHONY: core-restart
core-restart:
	/etc/init.d/core-daemon stop
	daemon/sbin/core-cleanup
	rm -f /var/log/core-daemon.log
	/etc/init.d/core-daemon start
