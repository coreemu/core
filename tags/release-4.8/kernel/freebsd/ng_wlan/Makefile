#
# (c)2006-2011 the Boeing Company
#
# ng_wlan
#
.if !defined(PLATFORM)
#PLATFORM=i386
PLATFORM=amd64
.endif

CFLAGS+=-I/usr/src/sys/${PLATFORM}/compile/CORE -DMULTICAST_LOOKUPS
# FreeBSD 4.11 is "FreeBSD" and 7.0 is "freebsd7.0"

#.if defined(OSTYPE)
#.if (${OSTYPE} == "FreeBSD")
#CFLAGS+=-DFREEBSD411
#.endif
#.endif

KMOD=		ng_wlan

SRCS= 		ng_wlan.c

#MAN=		ng_wlan.4

.include <bsd.kmod.mk>

