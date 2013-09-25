Author: Tom Goff <thomas.goff@boeing.com>

The Makefile is basically a wrapper around the make-kpkg command that
simplifies building kernel packages.  Running make will do some basic
dependency checks then build architecture appropriate kernel packages that
include changes from the patches directory.  The nfnetlink patch is what
virtualizes the netfilter queue mechanism; the flow-cache patch allows using
IPsec between network namespaces; the ifindex patch virtualizes network
interface index numbers.
