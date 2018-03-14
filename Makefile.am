# CORE
# (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Top-level Makefile for CORE project.
#

if WANT_DOCS
  DOCS = doc
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
	     Changelog \
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

define fpm-python =
fpm -s python -t $1 \
	-m "$(PACKAGE_MAINTAINERS)" \
	--vendor "$(PACKAGE_VENDOR)" \
	$2
endef

define fpm-gui =
fpm -s dir -t $1 -n core-gui \
	-m "$(PACKAGE_MAINTAINERS)" \
	--license "BSD" \
	--description "Common Open Research Emulator GUI front-end" \
	--url http://www.nrl.navy.mil/itd/ncs/products/core \
	--vendor "$(PACKAGE_VENDOR)" \
	-p core-gui_VERSION_ARCH.$1 \
	-v $(PACKAGE_VERSION) \
	-d "bash" \
	-d "tcl" \
	-d "tk" \
	$2 \
	-C $(DESTDIR)
endef

define fpm-daemon-rpm =
fpm -s python -t rpm \
	-p NAME_sysv_VERSION_ARCH.rpm \
	--rpm-init scripts/core-daemon \
	--python-install-bin $(bindir) \
	--python-install-data $(prefix) \
	--python-install-lib $(pythondir) \
	-m "$(PACKAGE_MAINTAINERS)" \
	--vendor "$(PACKAGE_VENDOR)" \
	-d "procps-ng" \
	-d "bash >= 3.0" \
	-d "bridge-utils" \
	-d "ebtables" \
	-d "iproute" \
	-d "libev" \
	-d "net-tools" \
	-d "python >= 2.7, python < 3.0" \
	netns/setup.py daemon/setup.py
endef

define fpm-daemon-deb =
fpm -s python -t deb \
	-p NAME_$1_VERSION_ARCH.deb \
	--python-install-bin $(bindir) \
	--python-install-data $(prefix) \
	--python-install-lib $(pythondir) \
	$2 $3 \
	-m "$(PACKAGE_MAINTAINERS)" \
	--vendor "$(PACKAGE_VENDOR)" \
	-d "procps" \
	-d "libc6 >= 2.14" \
	-d "bash >= 3.0" \
	-d "bridge-utils" \
	-d "ebtables" \
	-d "iproute2" \
	-d "libev4" \
	-d "python (>= 2.7), python (<< 3.0)" \
	--deb-recommends quagga \
	netns/setup.py daemon/setup.py
endef

.PHONY: fpm
fpm: clean-local-fpm
	$(MAKE) -C gui install DESTDIR=$(DESTDIR)
	$(call fpm-gui,rpm,-d "tkimg")
	$(call fpm-gui,deb,-d "libtk-img")
	$(call fpm-python,rpm,ns3/setup.py)
	$(call fpm-python,deb,ns3/setup.py)
	$(call fpm-daemon-rpm)
	$(call fpm-daemon-deb,sysv,--deb-init,scripts/core-daemon)
	$(call fpm-daemon-deb,systemd,--deb-systemd,scripts/core-daemon.service)

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
	$(call change-files,daemon/core/constants.py)
