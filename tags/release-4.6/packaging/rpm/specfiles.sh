#!/bin/sh

OLDDIR=$PWD
cd ../../

if [ ! -e Makefile ]; then
    echo "Missing file: Makefile"
fi
VER=`grep PACKAGE_VERSION Makefile | awk '{ print $3 }'`
echo "Detected CORE version $VER."

DESTDIR=/tmp/corerpmspec make install
if [ $? != 0 ]; then
    exit 1
fi
cd /tmp/corerpmspec
find . -type f  | sort > newspecfiles.log
# append all .py files with .py* so .pyc files are uninstalled
sed -i 's/\.py$/.py*/g' newspecfiles.log
# directory replacements
sed -i 's/^\.\//\//g' newspecfiles.log
sed -i 's/\/usr\/bin/%{_bindir}/g' newspecfiles.log
sed -i 's/\/usr\/sbin/%{_sbindir}/g' newspecfiles.log
sed -i 's/\/usr\/lib64\/python2.7\/site-packages/%{python_sitearch}/g' newspecfiles.log
sed -i 's/\/usr\/lib\/python2.7\/site-packages/%{python_sitelib}/g' newspecfiles.log
sed -i 's/\/usr\/lib\/python2.7\/dist-packages/%{python_sitelib}/g' newspecfiles.log
sed -i 's/\/usr\/lib\/core/@CORE_LIB_DIR@/g' newspecfiles.log
sed -i 's/\/usr\/share\/applications/%{_datadir}\/applications/g' newspecfiles.log
sed -i 's/\/usr\/share\/pixmaps/%{_datadir}\/pixmaps/g' newspecfiles.log
sed -i 's/\/usr\/share\/core/%{_datadir}\/%{name}/g' newspecfiles.log
sed -i 's/\/etc\/core/%config @CORE_CONF_DIR@/g' newspecfiles.log
sed -i 's/py2.7.egg/py@PYTHON_VERSION@.egg/g' newspecfiles.log
sed -i "s/$VER/@COREDPY_VERSION@/g" newspecfiles.log
sed -i 's/\/usr\/share\/man/%doc  %{_mandir}/g' newspecfiles.log
sed -i 's/\.1$/.1.gz/g' newspecfiles.log

echo .
echo A new filelist is available here:
ls -al /tmp/corerpmspec/newspecfiles.log
echo .
cd $OLDDIR
