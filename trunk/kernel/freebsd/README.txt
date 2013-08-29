CORE kernel patches

For information on the kernel modules ng_pipe and ng_wlan, see the README files in their respective directories. You should run the make && make install from
the module directories for CORE to work properly.

FreeBSD 8.x requires the small patches to allow per-node directories.

The FreeBSD 7.x version of CORE does not require the patch included here.
Instead you should download the latest vimage_7 kernel from:
  http://imunes.net/virtnet/

The FreeBSD 4.11 version of CORE requires the included patch to work. See the
CORE manual for patching details.

ng_pipe                      module you should install with FreeBSD 4.11 or 7.x
ng_wlan                      module you should install with FreeBSD 4.11 or 7.x
4.11-R-CORE.diff             patch you should use with FreeBSD 4.11
freebsd7-config-CORE         config that you may use with vimage_7 kernels
freebsd7-config-COREDEBUG    debugging config for use with vimage_7 kernels
vimage_7-CORE.diff           patch to add multicast routing to vimage_7_20081015
imunes-8.0-RELEASE.diff      per-node directories, persistent hub/switch, and
                             traffic snopping for wireshark for FreeBSD 8.0
symlinks-8.1-RELEASE.diff    per-node directories for FreeBSD 8.1

