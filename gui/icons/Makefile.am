# CORE
# (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#

TINY_ICONS := $(wildcard tiny/*)
NORM_ICONS := $(wildcard normal/*)
SVG_ICONS := $(wildcard svg/*)

# Icon files (/usr/local/share/core/icons/[tiny,normal,svg])
coreiconnormaldir = $(CORE_DATA_DIR)/icons/normal
dist_coreiconnormal_DATA = $(NORM_ICONS)

coreicontinydir	= $(CORE_DATA_DIR)/icons/tiny
dist_coreicontiny_DATA = $(TINY_ICONS)

coreiconsvgdir = $(CORE_DATA_DIR)/icons/svg
dist_coreiconsvg_DATA = $(SVG_ICONS)

iconpixmapdir = $(datarootdir)/pixmaps
dist_iconpixmap_DATA = core-gui.xpm

icondesktopdir = $(datarootdir)/applications
dist_icondesktop_DATA = core-gui.desktop

# extra cruft to remove
DISTCLEANFILES	= Makefile.in
