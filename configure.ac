#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.

# this defines the CORE version number, must be static for AC_INIT
AC_INIT(core, 9.2.1)

# autoconf and automake initialization
AC_CONFIG_SRCDIR([netns/version.h.in])
AC_CONFIG_AUX_DIR(config)
AC_CONFIG_MACRO_DIR(config)
AC_CONFIG_HEADERS([config.h])
AM_INIT_AUTOMAKE([tar-ustar])

# define variables used for packaging and date display
PACKAGE_DATE=m4_esyscmd_s([date +%Y%m%d])
PACKAGE_VENDOR="CORE Developers"
PACKAGE_MAINTAINERS="$PACKAGE_VENDOR"

# core specific variables
CORE_CONF_DIR="/opt/core/etc"
CORE_DATA_DIR="/opt/core/share"

AC_SUBST(PACKAGE_DATE)
AC_SUBST(PACKAGE_MAINTAINERS)
AC_SUBST(PACKAGE_VENDOR)
AC_SUBST(CORE_CONF_DIR)
AC_SUBST(CORE_DATA_DIR)

# documentation option
AC_ARG_ENABLE([docs],
	       [AS_HELP_STRING([--enable-docs[=ARG]],
		[build python documentation (default is no)])],
		[], [enable_docs=no])
AC_SUBST(enable_docs)

# python option
AC_ARG_ENABLE([python],
	       [AS_HELP_STRING([--enable-python[=ARG]],
		[build and install the python bindings (default is yes)])],
		[], [enable_python=yes])
AC_SUBST(enable_python)
if test "x$enable_python" = "xyes" ; then
  want_python=yes
else
  want_python=no
fi

AC_ARG_ENABLE([daemon],
	       [AS_HELP_STRING([--enable-daemon[=ARG]],
		[build and install the daemon with Python modules
		 (default is yes)])],
		[], [enable_daemon=yes])
AC_SUBST(enable_daemon)

AC_ARG_ENABLE([vnodedonly],
	       [AS_HELP_STRING([--enable-vnodedonly[=ARG]],
		[only try to build vnoded and vcmd container utils
		 (default is no)])],
		[enable_vnodedonly=yes], [enable_vnodedonly=no])
AC_SUBST(enable_vnodedonly)

SEARCHPATH="/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/sbin:/usr/local/bin"

# default compiler flags
# _GNU_SOURCE is defined to get c99 defines for lrint()
CFLAGS="$CFLAGS -O3 -Werror -Wall -D_GNU_SOURCE"

# checks for programs
AC_PROG_AWK
AC_PROG_CC
AC_PROG_INSTALL
AC_PROG_MAKE_SET
AC_PROG_RANLIB
AC_PROG_SED

want_python=no
want_linux_netns=no
if test "x$enable_daemon" = "xyes"; then
  want_python=yes
  want_linux_netns=yes

  AM_PATH_PYTHON(3.10)
  AS_IF([./venv/bin/python -m grpc_tools.protoc -h &> /dev/null], [], [AC_MSG_ERROR([grpc tools must be setup in venv, try setup.sh])])

  AC_CHECK_PROG(sysctl_path, sysctl, $as_dir, no, $SEARCHPATH)
  if test "x$sysctl_path" = "xno" ; then
    AC_MSG_ERROR([Could not locate sysctl (from procps package).])
  fi

  AC_CHECK_PROG(nftables_path, nft, $as_dir, no, $SEARCHPATH)
  if test "x$nftables_path" = "xno" ; then
    AC_MSG_ERROR([Could not locate nftables (from nftables package).])
  fi

  AC_CHECK_PROG(ip_path, ip, $as_dir, no, $SEARCHPATH)
  if test "x$ip_path" = "xno" ; then
    AC_MSG_ERROR([Could not locate ip (from iproute package).])
  fi

  AC_CHECK_PROG(tc_path, tc, $as_dir, no, $SEARCHPATH)
  if test "x$tc_path" = "xno" ; then
    AC_MSG_ERROR([Could not locate tc (from iproute package).])
  fi

  AC_CHECK_PROG(ethtool_path, ethtool, $as_dir, no, $SEARCHPATH)
  if test "x$ethtool_path" = "xno" ; then
    AC_MSG_ERROR([Could not locate ethtool (from package ethtool)])
  fi

  AC_CHECK_PROG(mount_path, mount, $as_dir, no, $SEARCHPATH)
  if test "x$mount_path" = "xno" ; then
    AC_MSG_ERROR([Could not locate mount (from package mount)])
  fi

  AC_CHECK_PROG(umount_path, umount, $as_dir, no, $SEARCHPATH)
  if test "x$umount_path" = "xno" ; then
    AC_MSG_ERROR([Could not locate umount (from package mount)])
  fi

  AC_CHECK_PROG(convert, convert, yes, no, $SEARCHPATH)
  if test "x$convert" = "xno" ; then
    AC_MSG_WARN([Could not locate ImageMagick convert.])
  fi

  AC_CHECK_PROG(ovs_vs_path, ovs-vsctl, $as_dir, no, $SEARCHPATH)
  if test "x$ovs_vs_path" = "xno" ; then
    AC_MSG_WARN([Could not locate ovs-vsctl cannot use OVS mode])
  fi

  AC_CHECK_PROG(ovs_of_path, ovs-ofctl, $as_dir, no, $SEARCHPATH)
  if test "x$ovs_of_path" = "xno" ; then
    AC_MSG_WARN([Could not locate ovs-ofctl cannot use OVS mode])
  fi
fi

if [ test "x$enable_daemon" = "xyes" || test "x$enable_vnodedonly" = "xyes" ] ; then
  want_linux_netns=yes

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
fi

want_docs=no
if [test "x$want_python" = "xyes" && test "x$enable_docs" = "xyes"] ; then
  AC_CHECK_PROG(help2man, help2man, yes, no, $SEARCHPATH)

  if test "x$help2man" = "xno" ; then
    AC_MSG_WARN([Could not locate help2man.])
    want_docs_missing="$want_docs_missing help2man"
  fi

  if test "x$want_docs_missing" = "x" ; then
    want_docs=yes
  else
    AC_MSG_ERROR([Could not find required helper utilities (${want_docs_missing}) so the CORE documentation will not be built.])
    want_docs=no
  fi

  # check for sphinx required during make
  AC_CHECK_PROG(sphinxapi_path, sphinx-apidoc, $as_dir, no, $SEARCHPATH)
  if test "x$sphinxapi_path" = "xno" ; then
    AC_MSG_ERROR(["Could not locate sphinx-apidoc, install python3 -m pip install sphinx"])
    want_docs=no
  fi
  AS_IF([$PYTHON -c "import sphinx_rtd_theme" &> /dev/null], [], [AC_MSG_ERROR([doc dependency missing, please install python3 -m pip install sphinx-rtd-theme])])
fi

# Variable substitutions
AM_CONDITIONAL(WANT_DAEMON, test x$enable_daemon = xyes)
AM_CONDITIONAL(WANT_DOCS, test x$want_docs = xyes)
AM_CONDITIONAL(WANT_PYTHON, test x$want_python = xyes)
AM_CONDITIONAL(WANT_NETNS, test x$want_linux_netns = xyes)
AM_CONDITIONAL(WANT_VNODEDONLY, test x$enable_vnodedonly = xyes)

if test $cross_compiling = no; then
  AM_MISSING_PROG(HELP2MAN, help2man)
else
  HELP2MAN=:
fi

# Output files
AC_CONFIG_FILES([Makefile
		man/Makefile
		docs/Makefile
		daemon/Makefile
		daemon/doc/Makefile
		daemon/doc/conf.py
		daemon/proto/Makefile
		netns/Makefile
		netns/version.h],)
AC_OUTPUT

# Summary text
echo \
"------------------------------------------------------------------------
${PACKAGE_STRING} Configuration:

Build:
  Host System Type:           ${host}
  C Compiler and flags:       ${CC} ${CFLAGS}
  Prefix:                     ${prefix}
  Exec Prefix:                ${exec_prefix}

Daemon:
  Daemon path:                ${bindir}
  Daemon config:              ${CORE_CONF_DIR}
  Python:                     ${PYTHON}

Features to build:
  Build Daemon:               ${enable_daemon}
  Documentation:              ${want_docs}

------------------------------------------------------------------------"

if test "x${want_linux_netns}" = "xyes" ; then
  echo "On this platform you should run core-gui as a normal user.
------------------------------------------------------------------------"
fi

