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

TCL_FILES := $(wildcard *.tcl)
ADDONS_FILES := $(wildcard addons/*)
CONFIG_FILES := $(wildcard configs/*)

# CORE GUI script (/usr/local/bin/core-gui)
dist_bin_SCRIPTS = core-gui

# Tcl/Tk scripts (/usr/local/lib/core)
coredir	= $(CORE_LIB_DIR)
dist_core_DATA = $(TCL_FILES)
dist_core_SCRIPTS = $(OTHER_FILES)

# Addon files
coreaddonsdir = $(coredir)/addons
dist_coreaddons_DATA = $(ADDONS_FILES)

# Sample configs (/usr/local/share/core/examples/configs)
coreconfigsdir = $(datadir)/core/examples/configs
dist_coreconfigs_DATA = $(CONFIG_FILES)

# remove generated file from dist
dist-hook:
	-rm -f $(distdir)/version.tcl

# extra cruft to remove
DISTCLEANFILES = Makefile.in

# files to include in source tarball not included elsewhere
EXTRA_DIST = core-gui.in
