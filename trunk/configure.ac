#
# Copyright (c) 2010-2013 the Boeing Company
# See the LICENSE file included in this distribution.
#
# CORE configure script
#
# author:  Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.

#
# this defines the CORE version number, must be static for AC_INIT
#
AC_INIT(core, 4.7, core-dev@pf.itd.nrl.navy.mil)
VERSION=$PACKAGE_VERSION
CORE_VERSION=$PACKAGE_VERSION
CORE_VERSION_DATE=20140806
COREDPY_VERSION=$PACKAGE_VERSION

#
# autoconf and automake initialization
#
AC_CONFIG_SRCDIR([daemon/src/version.h.in])
AC_CONFIG_AUX_DIR(config)
AC_CONFIG_MACRO_DIR(config)
AC_CONFIG_HEADERS([config.h])
AM_INIT_AUTOMAKE

AC_SUBST(CORE_VERSION)
AC_SUBST(CORE_VERSION_DATE)
AC_SUBST(COREDPY_VERSION)

#
# some of the following directory variables are not expanded at configure-time,
# so we have special checks to expand them
#

# CORE GUI files in LIBDIR
# AC_PREFIX_DEFAULT is /usr/local, but not expanded yet
if test "x$prefix" = "xNONE" ; then
  prefix="/usr/local"
fi
if test "$libdir" = "\${exec_prefix}/lib" ; then
  libdir="${prefix}/lib"
fi
# this can be /usr/lib or /usr/lib64
LIB_DIR="${libdir}"
# don't let the Tcl files install to /usr/lib64/core
CORE_LIB_DIR="${prefix}/lib/core"
AC_SUBST(LIB_DIR)
AC_SUBST(CORE_LIB_DIR)
SBINDIR="${prefix}/sbin"
AC_SUBST(SBINDIR)
BINDIR="${prefix}/bin"
AC_SUBST(BINDIR)

# CORE daemon configuration file (core.conf) in CORE_CONF_DIR
if test "$sysconfdir" = "\${prefix}/etc" ; then
  sysconfdir="/etc"
  CORE_CONF_DIR="/etc/core"
else
  CORE_CONF_DIR="$sysconfdir/core"
fi
AC_SUBST(CORE_CONF_DIR)
if test "$datarootdir" = "\${prefix}/share" ; then
  datarootdir="${prefix}/share"
fi
CORE_DATA_DIR="$datarootdir/core"
AC_SUBST(CORE_DATA_DIR)

# CORE GUI configuration files and preferences in CORE_GUI_CONF_DIR
# scenario files in ~/.core/configs/
#AC_ARG_VAR(CORE_GUI_CONF_DIR, [GUI configuration directory.])
AC_ARG_WITH([guiconfdir],
	    [AS_HELP_STRING([--with-guiconfdir=dir],
			    [specify GUI configuration directory])],
	    [CORE_GUI_CONF_DIR="$with_guiconfdir"], 
	    [CORE_GUI_CONF_DIR="\${HOME}/.core"])
AC_SUBST(CORE_GUI_CONF_DIR)
AC_ARG_ENABLE([gui],
	       [AS_HELP_STRING([--enable-gui[=ARG]],
		[build and install the GUI (default is yes)])],
		[], [enable_gui=yes])
AC_SUBST(enable_gui)
AC_ARG_ENABLE([daemon],
	       [AS_HELP_STRING([--enable-daemon[=ARG]],
		[build and install the daemon with Python modules
		 (default is yes)])],
		[], [enable_daemon=yes])
AC_SUBST(enable_daemon)
if test "x$enable_daemon" = "xno"; then
    want_python=no
    want_bsd=no
    want_linux_netns=no
fi

# CORE state files
if test "$localstatedir" = "\${prefix}/var" ; then
  # use /var instead of /usr/local/var (/usr/local/var/log isn't standard)
  CORE_STATE_DIR="/var"
else
  CORE_STATE_DIR="$localstatedir"
fi
AC_SUBST(CORE_STATE_DIR)

# default compiler flags
# _GNU_SOURCE is defined to get c99 defines for lrint()
CFLAGS="$CFLAGS -O3 -Werror -Wall -D_GNU_SOURCE"
# debug flags
#CFLAGS="$CFLAGS -g -Werror -Wall -D_GNU_SOURCE"

# Checks for programs.
AC_PROG_AWK
AC_PROG_CC
AC_PROG_INSTALL
AC_PROG_MAKE_SET
AC_PROG_RANLIB

AM_PATH_PYTHON(2.6, want_python=yes, want_python=no)
SEARCHPATH="/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/sbin:/usr/local/bin"
#
# daemon dependencies
#
if test "x$enable_daemon" = "xyes" ; then
  AC_CHECK_PROG(brctl_path, brctl, $as_dir, no, $SEARCHPATH)
  AC_CHECK_PROG(sysctl_path, sysctl, $as_dir, no, $SEARCHPATH)
  AC_CHECK_PROG(ebtables_path, ebtables, $as_dir, no, $SEARCHPATH)
  AC_CHECK_PROG(ip_path, ip, $as_dir, no, $SEARCHPATH)
  AC_CHECK_PROG(tc_path, tc, $as_dir, no, $SEARCHPATH)
  AC_CHECK_PROG(ifconfig_path, ifconfig, $as_dir, no, $SEARCHPATH)
  AC_CHECK_PROG(ngctl_path, ngctl, $as_dir, no, $SEARCHPATH)
  AC_CHECK_PROG(vimage_path, vimage, $as_dir, no, $SEARCHPATH)
  AC_CHECK_PROG(mount_path, mount, $as_dir, no, $SEARCHPATH)
  AC_CHECK_PROG(umount_path, umount, $as_dir, no, $SEARCHPATH)
  AC_CHECK_PROG(convert, convert, yes, no, $SEARCHPATH)
fi

#AC_CHECK_PROG(dia, dia, yes, no)
AC_CHECK_PROG(help2man, help2man, yes, no, $SEARCHPATH)
if test "x$convert" = "xno" ; then
    AC_MSG_WARN([Could not locate ImageMagick convert.])
    #want_docs_missing="convert"
fi
#if test "x$dia" = "xno" ; then
#    AC_MSG_WARN([Could not locate dia.])
#    want_docs_missing="dia"
#fi
if test "x$help2man" = "xno" ; then
    AC_MSG_WARN([Could not locate help2man.])
    want_docs_missing="$want_docs_missing help2man"
fi
if test "x$want_docs_missing" = "x" ; then
  want_docs=yes
else
  AC_MSG_WARN([Could not find required helper utilities (${want_docs_missing}) so the CORE documentation will not be built.])
  want_docs=no
fi

#AC_PATH_PROGS(tcl_path, [tclsh tclsh8.5 tclsh8.4], no)
#if test "x$tcl_path" = "xno" ; then
#    AC_MSG_ERROR([Could not locate tclsh. Please install Tcl/Tk.])
#fi
#AC_PATH_PROGS(wish_path, [wish wish8.5 wish8.4], no)
#if test "x$wish_path" = "xno" ; then
#    AC_MSG_ERROR([Could not locate wish. Please install Tcl/Tk.])
#fi

if test "x$enable_daemon" = "xyes" ; then
  # Checks for libraries.
  AC_CHECK_LIB([netgraph], [NgMkSockNode])

  # Checks for header files.
  AC_CHECK_HEADERS([arpa/inet.h fcntl.h limits.h stdint.h stdlib.h string.h sys/ioctl.h sys/mount.h sys/socket.h sys/time.h termios.h unistd.h])

  # Checks for typedefs, structures, and compiler characteristics.
  AC_C_INLINE
  AC_TYPE_INT32_T
  AC_TYPE_PID_T
  AC_TYPE_SIZE_T
  AC_TYPE_SSIZE_T
  AC_TYPE_UINT32_T
  AC_TYPE_UINT8_T

  # Checks for library functions.
  AC_FUNC_FORK
  AC_FUNC_MALLOC
  AC_FUNC_REALLOC
  AC_CHECK_FUNCS([atexit dup2 gettimeofday memset socket strerror uname])
fi

# simple architecture detection
if test `uname -m` = "x86_64"; then
    ARCH=amd64
else
    ARCH=i386
fi
AC_MSG_RESULT([using architecture $ARCH])
AC_SUBST(ARCH)

# Host-specific detection
want_linux_netns=no
want_bsd=no
if test `uname -s` = "FreeBSD"; then
    want_bsd=yes
    AC_CHECK_PROGS(gmake)
    # FreeBSD fix for linking libev port below
    CFLAGS="$CFLAGS -L/usr/local/lib"
else
    want_linux_netns=yes
fi
if test "x$want_python" = "xno"; then
    want_bsd=no
    want_linux_netns=no
fi

if test "x$want_python" = "xyes"; then
    CFLAGS_save=$CFLAGS
    CPPFLAGS_save=$CPPFLAGS
    if test "x$PYTHON_INCLUDE_DIR" = "x"; then
	PYTHON_INCLUDE_DIR=`$PYTHON -c "import distutils.sysconfig; print distutils.sysconfig.get_python_inc()"`
    fi
    CFLAGS="-I$PYTHON_INCLUDE_DIR"
    CPPFLAGS="-I$PYTHON_INCLUDE_DIR"
    AC_CHECK_HEADERS([Python.h], [],
	AC_MSG_ERROR([Python bindings require Python development headers (try installing your 'python-devel' or 'python-dev' package)]))
    CFLAGS=$CFLAGS_save
    CPPFLAGS=$CPPFLAGS_save
    PKG_CHECK_MODULES(libev, libev,
        AC_MSG_RESULT([found libev using pkgconfig OK])
        AC_SUBST(libev_CFLAGS)
        AC_SUBST(libev_LIBS),
	AC_MSG_RESULT([did not find libev using pkconfig...])
	AC_CHECK_LIB([ev], ev_set_allocator,
	     AC_MSG_RESULT([found libev OK])
             AC_SUBST(libev_CFLAGS)
             AC_SUBST(libev_LIBS, [-lev]),
	     AC_MSG_ERROR([Python bindings require libev (try installing your 'libev-devel' or 'libev-dev' package)])))
else
    # Namespace support requires Python support
    want_linux_netns=no
fi

progs_missing=""
if test "x$want_linux_netns" = "xyes"; then
    if test "x$brctl_path" = "xno" ; then
	progs_missing="${progs_missing}brctl "
	brctl_path="/usr/sbin"
	AC_MSG_ERROR([Could not locate brctl (from bridge-utils package).])
    fi
    if test "x$ebtables_path" = "xno" ; then
	progs_missing="${progs_missing}ebtables "
	ebtables_path="/sbin"
	AC_MSG_ERROR([Could not locate ebtables (from ebtables package).])
    fi
    if test "x$ip_path" = "xno" ; then
	progs_missing="${progs_missing}ip "
	ip_path="/sbin"
	AC_MSG_ERROR([Could not locate ip (from iproute package).])
    fi
    if test "x$tc_path" = "xno" ; then
	progs_missing="${progs_missing}tc "
	tc_path="/sbin"
	AC_MSG_ERROR([Could not locate tc (from iproute package).])
    fi
fi
if test "x$want_bsd" = "xyes"; then
    if test "x$ifconfig_path" = "xno" ; then
	AC_MSG_ERROR([Could not locate the 'ifconfig' utility.])
    fi
    if test "x$ngctl_path" = "xno" ; then
	AC_MSG_ERROR([Could not locate the 'ngctl' utility.])
    fi
    if test "x$vimage_path" = "xno" ; then
	AC_MSG_ERROR([Could not locate the 'vimage' utility.])
    fi
fi

AC_ARG_WITH([startup],
	    [AS_HELP_STRING([--with-startup=option],
		[option=systemd,suse,none to install systemd/SUSE init scripts])],
	    [with_startup=$with_startup],
	    [with_startup=initd])
AC_SUBST(with_startup)
AC_MSG_RESULT([using startup option $with_startup])

# Variable substitutions
AM_CONDITIONAL(WANT_GUI, test x$enable_gui = xyes)
AM_CONDITIONAL(WANT_DAEMON, test x$enable_daemon = xyes)
AM_CONDITIONAL(WANT_BSD, test x$want_bsd = xyes)
AM_CONDITIONAL(WANT_DOCS, test x$want_docs = xyes)
AM_CONDITIONAL(WANT_PYTHON, test x$want_python = xyes)
AM_CONDITIONAL(WANT_NETNS, test x$want_linux_netns = xyes)

AM_CONDITIONAL(WANT_INITD, test x$with_startup = xinitd)
AM_CONDITIONAL(WANT_SYSTEMD, test x$with_startup = xsystemd)
AM_CONDITIONAL(WANT_SUSE, test x$with_startup = xsuse)

if test $cross_compiling = no; then
  AM_MISSING_PROG(HELP2MAN, help2man)
else
  HELP2MAN=:
fi


# Output files
AC_CONFIG_FILES([Makefile
		gui/core-gui
		gui/version.tcl
		gui/Makefile
		gui/icons/Makefile
		scripts/Makefile
		scripts/perf/Makefile
		scripts/xen/Makefile
		doc/Makefile
		doc/conf.py
		doc/man/Makefile
		doc/figures/Makefile
		daemon/Makefile
		daemon/src/Makefile
		daemon/src/version.h
		daemon/core/constants.py
		daemon/ns3/Makefile
		daemon/ns3/corens3/constants.py
		daemon/doc/Makefile
		daemon/doc/conf.py
		packaging/deb/core-daemon.install
		packaging/deb/core-gui.install
		packaging/rpm/core.spec],)
AC_OUTPUT

# Summary text
echo \
"------------------------------------------------------------------------
${PACKAGE_STRING} Configuration:

  Host System Type:           ${host}
  C Compiler and flags:       ${CC} ${CFLAGS}
  Install prefix:             ${prefix}
  Build GUI:                  ${enable_gui}
  GUI path:                   ${CORE_LIB_DIR}
  GUI config:                 ${CORE_GUI_CONF_DIR}
  Daemon path:                ${SBINDIR}
  Daemon config:              ${CORE_CONF_DIR}
  Python modules:             ${pythondir}
  Logs:                       ${CORE_STATE_DIR}/log

Features to build:
  Python bindings:            ${want_python}
  Linux Namespaces emulation: ${want_linux_netns}
  FreeBSD Jails emulation:    ${want_bsd}
  Documentation:              ${want_docs}

------------------------------------------------------------------------"
if test "x${want_bsd}" = "xyes" ; then
  # TODO: more sophisticated checks of gmake vs make
  echo ">>> NOTE: on FreeBSD you should use 'gmake' instead of 'make'
------------------------------------------------------------------------"
fi
if test "x${want_linux_netns}" = "xyes" ; then
  echo "On this platform you should run core-gui as a normal user.
------------------------------------------------------------------------"
fi
if test "x${progs_missing}" != "x" ; then
  echo ">>> NOTE: the following programs could not be found:"
  echo "          $progs_missing
------------------------------------------------------------------------"
fi
