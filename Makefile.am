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
  DAEMON = scripts daemon
endif

if WANT_NETNS
  NETNS = netns ns3
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


if PYTHON3
PYTHON_DEP = python >= 3.0
else
PYTHON_DEP = python >= 2.7, python < 3.0
endif

define fpm-rpm =
fpm -s dir -t rpm -n core \
	-m "$(PACKAGE_MAINTAINERS)" \
	--license "BSD" \
	--description "Common Open Research Emulator" \
	--url https://github.com/coreemu/core \
	--vendor "$(PACKAGE_VENDOR)" \
	-p core_$(PYTHON)_VERSION_ARCH.rpm \
	-v $(PACKAGE_VERSION) \
	--rpm-init scripts/core-daemon \
	-d "tcl" \
	-d "tk" \
	-d "procps-ng" \
	-d "bash >= 3.0" \
	-d "bridge-utils" \
	-d "ebtables" \
	-d "iproute" \
	-d "libev" \
	-d "net-tools" \
	-d "$(PYTHON_DEP)" \
	-C $(DESTDIR)
endef

define fpm-deb =
fpm -s dir -t deb -n core \
	-m "$(PACKAGE_MAINTAINERS)" \
	--license "BSD" \
	--description "Common Open Research Emulator" \
	--url https://github.com/coreemu/core \
	--vendor "$(PACKAGE_VENDOR)" \
	-p core_$(PYTHON)_VERSION_ARCH.deb \
	-v $(PACKAGE_VERSION) \
	--deb-systemd scripts/core-daemon.service \
	-d "tcl" \
	-d "tk" \
	-d "libtk-img" \
	-d "procps" \
	-d "libc6 >= 2.14" \
	-d "bash >= 3.0" \
	-d "bridge-utils" \
	-d "ebtables" \
	-d "iproute2" \
	-d "libev4" \
	-d "$(PYTHON_DEP)" \
	-C $(DESTDIR)
endef

.PHONY: fpm
fpm: clean-local-fpm
	$(MAKE) install DESTDIR=$(DESTDIR)
	$(call fpm-deb)
	$(call fpm-rpm)

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
	-e 's,[@]pythondir[@],$(pythondir),g' \
	-e 's,[@]PYTHON[@],$(PYTHON),g' \
	-e 's,[@]PACKAGE_VERSION[@],$(PACKAGE_VERSION),g' \
	-e 's,[@]PACKAGE_DATE[@],$(PACKAGE_DATE),g' \
	-e 's,[@]CORE_LIB_DIR[@],$(CORE_LIB_DIR),g' \
	-e 's,[@]CORE_STATE_DIR[@],$(CORE_STATE_DIR),g' \
	-e 's,[@]CORE_DATA_DIR[@],$(CORE_DATA_DIR),g' \
	-e 's,[@]CORE_CONF_DIR[@],$(CORE_CONF_DIR),g' \
	-e 's,[@]CORE_GUI_CONF_DIR[@],$(CORE_GUI_CONF_DIR),g' \
	-e 's,[@]brctl_path[@],$(brctl_path),g' \
	-e 's,[@]sysctl_path[@],$(sysctl_path),g' \
	-e 's,[@]ip_path[@],$(ip_path),g' \
	-e 's,[@]tc_path[@],$(tc_path),g' \
	-e 's,[@]ebtables_path[@],$(ebtables_path),g' \
	-e 's,[@]mount_path[@],$(mount_path),g' \
	-e 's,[@]umount_path[@],$(umount_path),g' \
	-e 's,[@]ovs_vs_path[@],$(ovs_vs_path),g' \
	-e 's,[@]ovs_of_path[@],$(ovs_of_path),g' \
	< $1.in > $1
endef

all: change-files

.PHONY: change-files
change-files:
	$(call change-files,gui/core-gui)
	$(call change-files,scripts/core-daemon.service)
	$(call change-files,scripts/core-daemon)
	$(call change-files,daemon/core/constants.py)
	$(call change-files,ns3/setup.py)
	$(call change-files,netns/setup.py)
	$(call change-files,daemon/setup.py)

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
