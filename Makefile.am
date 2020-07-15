# CORE
# Top-level Makefile for CORE project.
#

if WANT_DOCS
  DOCS = docs man
endif

if WANT_GUI
  GUI = gui
endif

if WANT_DAEMON
  DAEMON = daemon
endif

if WANT_NETNS
  NETNS = netns
endif

# keep docs last due to dependencies on binaries
SUBDIRS = $(GUI) $(DAEMON) $(NETNS) $(DOCS)

ACLOCAL_AMFLAGS = -I config

# extra files to include with distribution tarball
EXTRA_DIST = bootstrap.sh \
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
	-p core_distributed_VERSION_ARCH.deb \
	-v $(PACKAGE_VERSION) \
	-d "ethtool" \
	-d "procps" \
	-d "libc6 >= 2.14" \
	-d "bash >= 3.0" \
	-d "ebtables" \
	-d "iproute2" \
	-d "libev4" \
	-d "openssh-server" \
	-d "xterm" \
	-C $(DESTDIR)
endef

define fpm-distributed-rpm =
fpm -s dir -t rpm -n core-distributed \
	-m "$(PACKAGE_MAINTAINERS)" \
	--license "BSD" \
	--description "Common Open Research Emulator Distributed Package" \
	--url https://github.com/coreemu/core \
	--vendor "$(PACKAGE_VENDOR)" \
	-p core_distributed_VERSION_ARCH.rpm \
	-v $(PACKAGE_VERSION) \
	-d "ethtool" \
	-d "procps-ng" \
	-d "bash >= 3.0" \
	-d "ebtables" \
	-d "iproute" \
	-d "libev" \
	-d "net-tools" \
	-d "openssh-server" \
	-d "xterm" \
	-C $(DESTDIR)
endef

.PHONY: fpm-distributed
fpm-distributed: clean-local-fpm
	$(MAKE) -C netns install DESTDIR=$(DESTDIR)
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
	-e 's,[@]CORE_GUI_CONF_DIR[@],$(CORE_GUI_CONF_DIR),g' \
	< $1.in > $1
endef

all: change-files

.PHONY: change-files
change-files:
	$(call change-files,gui/core-gui)
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
