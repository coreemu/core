# CORE
# (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#

TINY_ICONS =	tiny/button.play.gif \
		tiny/select.gif tiny/marker.gif \
		tiny/rj45.gif tiny/text.gif \
		tiny/edit-delete.gif tiny/stop.gif \
		tiny/blank.gif tiny/mobility.gif \
		tiny/script_play.gif tiny/arrow.gif \
		tiny/lanswitch.gif tiny/script_pause.gif \
		tiny/pc.gif tiny/rectangle.gif \
		tiny/observe.gif tiny/document-new.gif \
		tiny/document-save.gif \
		tiny/view-refresh.gif tiny/moboff.gif \
		tiny/document-properties.gif tiny/arrow.up.gif \
		tiny/host.gif tiny/hub.gif \
		tiny/twonode.gif tiny/router.gif \
		tiny/eraser.gif \
		tiny/stock_connect.gif tiny/stock_disconnect.gif \
		tiny/ping.gif tiny/link.gif \
		tiny/start.gif \
		tiny/trace.gif tiny/button.stop.gif \
		tiny/arrow.down.gif tiny/oval.gif \
		tiny/wlan.gif tiny/delete.gif \
		tiny/run.gif tiny/tunnel.gif \
		tiny/script_stop.gif \
		tiny/router_black.gif tiny/router_green.gif \
		tiny/router_red.gif tiny/router_yellow.gif \
		tiny/router_purple.gif \
		tiny/ap.gif tiny/mdr.gif \
		tiny/folder.gif \
		tiny/cel.gif \
		tiny/fileopen.gif \
		tiny/xen.gif \
		tiny/plot.gif

NORM_ICONS =	normal/gps-diagram.xbm \
		normal/router_black.gif normal/host.gif \
		normal/hub.gif \
		normal/router.gif \
		normal/rj45.gif normal/antenna.gif \
		normal/text.gif \
		normal/lanswitch.gif normal/core-icon.png \
		normal/core-icon.xbm normal/oval.gif \
		normal/wlan.gif normal/pc.gif \
		normal/tunnel.gif normal/core-logo-275x75.gif \
		normal/router_red.gif normal/router_green.gif \
		normal/simple.xbm \
		normal/document-properties.gif \
		normal/thumb-unknown.gif \
		normal/router_purple.gif normal/router_yellow.gif \
		normal/ap.gif normal/mdr.gif \
		normal/xen.gif

SVG_ICONS = 	svg/ap.svg \
		svg/cel.svg \
		svg/hub.svg \
		svg/lanswitch.svg \
		svg/mdr.svg \
		svg/otr.svg \
		svg/rj45.svg \
		svg/router_black.svg \
		svg/router_green.svg \
		svg/router_purple.svg \
		svg/router_red.svg \
		svg/router.svg \
		svg/router_yellow.svg \
		svg/start.svg \
		svg/tunnel.svg \
		svg/vlan.svg \
		svg/xen.svg

#
# Icon files (/usr/local/share/core/icons/[tiny,normal,svg])
#
coreiconnormaldir	= $(CORE_DATA_DIR)/icons/normal
dist_coreiconnormal_DATA = $(NORM_ICONS)
coreicontinydir		= $(CORE_DATA_DIR)/icons/tiny
dist_coreicontiny_DATA	= $(TINY_ICONS)
coreiconsvgdir		= $(CORE_DATA_DIR)/icons/svg
dist_coreiconsvg_DATA	= $(SVG_ICONS)

iconpixmapdir = $(datarootdir)/pixmaps
icondesktopdir = $(datarootdir)/applications

install-exec-hook: install-gui-icon

uninstall-hook: uninstall-gui-icon

.PHONY: install-gui-icon
install-gui-icon:
	test -d $(DESTDIR)/$(iconpixmapdir) || \
	    mkdir -p $(DESTDIR)/$(iconpixmapdir)
	cp -f core-gui.xpm $(DESTDIR)/$(iconpixmapdir)
	test -d $(DESTDIR)/$(icondesktopdir) || \
	    mkdir -p $(DESTDIR)/$(icondesktopdir)
	cp -f core-gui.desktop $(DESTDIR)/$(icondesktopdir)

.PHONY: uninstall-gui-icon
uninstall-gui-icon:
	rm -f $(iconpixmapdir)/core-gui.xpm
	rm -f $(icondesktopdir)/core-gui.desktop

EXTRA_DIST	= core-gui.xpm core-gui.desktop

# extra cruft to remove
DISTCLEANFILES	= Makefile.in
