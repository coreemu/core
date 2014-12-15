# CORE
# (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for installing the CORE GUI. Since it is a Tcl/Tk script, we do not
# build anything here.
#

SUBDIRS = icons

TCL_FILES	= annotations.tcl api.tcl canvas.tcl cfgparse.tcl \
		core.tcl debug.tcl editor.tcl exec.tcl \
		filemgmt.tcl gpgui.tcl \
		graph_partitioning.tcl help.tcl \
		initgui.tcl ipv4.tcl ipv6.tcl \
		linkcfg.tcl mobility.tcl nodecfg.tcl \
		nodes.tcl services.tcl ns2imunes.tcl plugins.tcl \
		tooltips.tcl topogen.tcl traffic.tcl util.tcl \
		version.tcl widget.tcl wlan.tcl wlanscript.tcl \
		exceptions.tcl

ADDONS_FILES    = addons/ipsecservice.tcl

CONFIG_FILES	= configs/sample1.imn configs/sample1.scen \
		configs/sample1-bg.gif configs/sample2-ssh.imn \
		configs/sample3-bgp.imn	configs/sample4-nrlsmf.imn \
		configs/sample4.scen configs/sample4-bg.jpg \
		configs/sample5-mgen.imn configs/sample6-emane-rfpipe.imn \
		configs/sample7-emane-ieee80211abg.imn \
		configs/sample8-ipsec-service.imn \
		configs/sample9-vpn.imn \
		configs/sample10-kitchen-sink.imn

OTHER_FILES	= core-bsd-cleanup.sh

#
# CORE GUI script (/usr/local/bin/core-gui)
#
dist_bin_SCRIPTS = core-gui

#
# Tcl/Tk scripts (/usr/local/lib/core)
#
coredir			= $(CORE_LIB_DIR)
dist_core_DATA		= $(TCL_FILES) 
dist_core_SCRIPTS	= $(OTHER_FILES)

#
# Addon files
#
coreaddonsdir		= $(coredir)/addons
dist_coreaddons_DATA = $(ADDONS_FILES)

#
# Sample configs (/usr/local/share/core/examples/configs)
#
coreconfigsdir		= $(datadir)/core/examples/configs
dist_coreconfigs_DATA	= $(CONFIG_FILES) 


dist-hook:
	rm -rf $(distdir)/addons/.svn

# extra cruft to remove
DISTCLEANFILES	= Makefile.in

# files to include in source tarball not included elsewhere
EXTRA_DIST 	= addons
