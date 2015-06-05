#
# (c)2008 the Boeing Company
#
# modified ng_pipe node
#
.if !defined(PLATFORM)
#PLATFORM=i386
PLATFORM=amd64
.endif

CFLAGS=-DBOEING_WLAN -I/usr/src/sys/${PLATFORM}/compile/CORE

KMOD=		ng_pipe

SRCS= 		ng_pipe.c

#MAN=		ng_pipe.4

# FreeBSD 4.11 is "FreeBSD" and 7.0 is "freebsd7.0"
#.if defined(OSTYPE)
#.if (${OSTYPE} == "FreeBSD")
#CFLAGS+=-DFREEBSD411
#SRCS=		ng_pipe_freebsd4.c
#.endif
#.endif

.include <bsd.kmod.mk>
