# CORE
# Top-level Makefile for CORE project.
#

if WANT_DOCS
  DOCS = docs man
endif

if WANT_DAEMON
  DAEMON = daemon
endif

if WANT_NETNS
  NETNS = netns
endif

# keep docs last due to dependencies on binaries
SUBDIRS = $(DAEMON) $(NETNS) $(DOCS)

ACLOCAL_AMFLAGS = -I config

# extra files to include with distribution tarball
EXTRA_DIST = bootstrap.sh \
		 package \
	     LICENSE \
	     README.md \
	     ASSIGNMENT_OF_COPYRIGHT.pdf \
	     CHANGELOG.md \
	     .version \
	     .version.date

DISTCLEAN_TARGETS = aclocal.m4 config.h.in

# extra cruft to remove
DISTCLEANFILES = aclocal.m4 \
		 config.h.in \
		 configure \
		 Makefile.in \
		 config/compile

MAINTAINERCLEANFILES = .version	\
		       .version.date

define fpm-distributed-deb =
fpm -s dir -t deb -n core-distributed \
	-m "$(PACKAGE_MAINTAINERS)" \
	--license "BSD" \
	--description "Common Open Research Emulator Distributed Package" \
	--url https://github.com/coreemu/core \
	--vendor "$(PACKAGE_VENDOR)" \
	-p core-distributed_VERSION_ARCH.deb \
	-v $(PACKAGE_VERSION) \
	-d "ethtool" \
	-d "procps" \
	-d "libc6 >= 2.14" \
	-d "bash >= 3.0" \
	-d "nftables" \
	-d "iproute2" \
	-d "libev4" \
	-d "openssh-server" \
	-d "xterm" \
	netns/vnoded=/usr/bin/ \
	netns/vcmd=/usr/bin/
endef

define fpm-distributed-rpm =
fpm -s dir -t rpm -n core-distributed \
	-m "$(PACKAGE_MAINTAINERS)" \
	--license "BSD" \
	--description "Common Open Research Emulator Distributed Package" \
	--url https://github.com/coreemu/core \
	--vendor "$(PACKAGE_VENDOR)" \
	-p core-distributed_VERSION_ARCH.rpm \
	-v $(PACKAGE_VERSION) \
	-d "ethtool" \
	-d "procps-ng" \
	-d "bash >= 3.0" \
	-d "nftables" \
	-d "iproute" \
	-d "libev" \
	-d "net-tools" \
	-d "openssh-server" \
	-d "xterm" \
	netns/vnoded=/usr/bin/ \
	netns/vcmd=/usr/bin/
endef

define fpm-rpm =
fpm -s dir -t rpm -n core \
	-m "$(PACKAGE_MAINTAINERS)" \
	--license "BSD" \
	--description "core vnoded/vcmd and system dependencies" \
	--url https://github.com/coreemu/core \
	--vendor "$(PACKAGE_VENDOR)" \
	-p core_VERSION_ARCH.rpm \
	-v $(PACKAGE_VERSION) \
	--rpm-init package/core-daemon \
	--after-install package/after-install.sh \
	--after-remove package/after-remove.sh \
	-d "ethtool" \
	-d "tk" \
	-d "procps-ng" \
	-d "bash >= 3.0" \
	-d "ebtables" \
	-d "iproute" \
	-d "libev" \
	-d "net-tools" \
	-d "nftables" \
	netns/vnoded=/usr/bin/ \
	netns/vcmd=/usr/bin/ \
	package/etc/core.conf=/etc/core/ \
	package/etc/logging.conf=/etc/core/ \
	package/examples=/opt/core/ \
	daemon/dist/core-$(PACKAGE_VERSION)-py3-none-any.whl=/opt/core/
endef

define fpm-deb =
fpm -s dir -t deb -n core \
	-m "$(PACKAGE_MAINTAINERS)" \
	--license "BSD" \
	--description "core vnoded/vcmd and system dependencies" \
	--url https://github.com/coreemu/core \
	--vendor "$(PACKAGE_VENDOR)" \
	-p core_VERSION_ARCH.deb \
	-v $(PACKAGE_VERSION) \
	--deb-systemd package/core-daemon.service \
	--deb-no-default-config-files \
	--after-install package/after-install.sh \
	--after-remove package/after-remove.sh \
	-d "ethtool" \
	-d "tk" \
	-d "libtk-img" \
	-d "procps" \
	-d "libc6 >= 2.14" \
	-d "bash >= 3.0" \
	-d "ebtables" \
	-d "iproute2" \
	-d "libev4" \
	-d "nftables" \
	netns/vnoded=/usr/bin/ \
	netns/vcmd=/usr/bin/ \
	package/etc/core.conf=/etc/core/ \
	package/etc/logging.conf=/etc/core/ \
	package/examples=/opt/core/ \
	daemon/dist/core-$(PACKAGE_VERSION)-py3-none-any.whl=/opt/core/
endef

.PHONY: fpm
fpm: clean-local-fpm
	cd daemon && poetry build -f wheel
	$(call fpm-deb)
	$(call fpm-rpm)
	$(call fpm-distributed-deb)
	$(call fpm-distributed-rpm)

.PHONY: clean-local-fpm
clean-local-fpm:
	-rm -rf *.deb
	-rm -rf *.rpm

clean-local: clean-local-fpm

.version: Makefile
	echo $(PACKAGE_VERSION) > $@

.version.date: Makefile
	echo $(PACKAGE_DATE) > $@

define change-files =
$(info creating file $1 from $1.in)
@$(SED) -e 's,[@]sbindir[@],$(sbindir),g' \
	-e 's,[@]bindir[@],$(bindir),g' \
	-e 's,[@]PACKAGE_VERSION[@],$(PACKAGE_VERSION),g' \
	-e 's,[@]PACKAGE_DATE[@],$(PACKAGE_DATE),g' \
	-e 's,[@]CORE_LIB_DIR[@],$(CORE_LIB_DIR),g' \
	-e 's,[@]CORE_STATE_DIR[@],$(CORE_STATE_DIR),g' \
	-e 's,[@]CORE_DATA_DIR[@],$(CORE_DATA_DIR),g' \
	-e 's,[@]CORE_CONF_DIR[@],$(CORE_CONF_DIR),g' \
	< $1.in > $1
endef

all: change-files

.PHONY: change-files
change-files:
	$(call change-files,daemon/core/constants.py)
	$(call change-files,netns/setup.py)

CORE_DOC_SRC = core-python-$(PACKAGE_VERSION)
.PHONY: doc
doc: doc-clean
	$(MAKE) -C daemon/doc html
	mv daemon/doc/_build/html daemon/doc/$(CORE_DOC_SRC)
	tar -C daemon/doc -czf $(CORE_DOC_SRC).tgz $(CORE_DOC_SRC)

.PHONY: doc-clean
doc-clean:
	-rm -rf daemon/doc/_build
	-rm -rf daemon/doc/$(CORE_DOC_SRC)
	-rm -f $(CORE_DOC_SRC).tgz
