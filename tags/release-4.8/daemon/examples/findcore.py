#!/usr/bin/env python
#
# Search for installed CORE library files and Python bindings.
#

import os, glob

pythondirs = [
 "/usr/lib/python2.7/site-packages",
 "/usr/lib/python2.7/dist-packages",
 "/usr/lib64/python2.7/site-packages",
 "/usr/lib64/python2.7/dist-packages",
 "/usr/local/lib/python2.7/site-packages",
 "/usr/local/lib/python2.7/dist-packages",
 "/usr/local/lib64/python2.7/site-packages",
 "/usr/local/lib64/python2.7/dist-packages",
 "/usr/lib/python2.6/site-packages",
 "/usr/lib/python2.6/dist-packages",
 "/usr/lib64/python2.6/site-packages",
 "/usr/lib64/python2.6/dist-packages",
 "/usr/local/lib/python2.6/site-packages",
 "/usr/local/lib/python2.6/dist-packages",
 "/usr/local/lib64/python2.6/site-packages",
 "/usr/local/lib64/python2.6/dist-packages",
 ]

tcldirs = [
 "/usr/lib/core",
 "/usr/local/lib/core",
 ]

def find_in_file(fn, search, column=None):
    ''' Find a line starting with 'search' in the file given by the filename 
        'fn'. Return True if found, False if not found, or the column text if
        column is specified.
    '''
    r = False
    if not os.path.exists(fn):
        return r
    f = open(fn, "r")
    for line in f:
        if line[:len(search)] != search:
            continue
        r = True
        if column is not None:
            r = line.split()[column]
        break
    f.close()
    return r

def main():
    versions = []
    for d in pythondirs:
        fn = "%s/core/constants.py" % d
        ver = find_in_file(fn, 'COREDPY_VERSION', 2)
        if ver:
            ver = ver.strip('"')
            versions.append((d, ver))
        for e in glob.iglob("%s/core_python*egg-info" % d):
            ver = find_in_file(e, 'Version:', 1)
            if ver:
                versions.append((e, ver))
        for e in glob.iglob("%s/netns*egg-info" % d):
            ver = find_in_file(e, 'Version:', 1)
            if ver:
                versions.append((e, ver))
    for d in tcldirs:
        fn = "%s/version.tcl" % d
        ver = find_in_file(fn, 'set CORE_VERSION', 2)
        if ver:
            versions.append((d, ver))

    for (d, ver) in versions:
        print "%8s  %s" % (ver, d)

if __name__ == "__main__":
    main()

