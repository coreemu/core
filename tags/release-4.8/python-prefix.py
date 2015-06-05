#!/usr/bin/env python

import sys
import os.path
import site

def main():
    '''\
    Check if the given prefix is included in sys.path for the given
    python version; if not find an alternate valid prefix.  Print the
    result to standard out.
    '''
    if len(sys.argv) != 3:
        msg = 'usage: %s <prefix> <python version>\n' % \
              os.path.basename(sys.argv[0])
        sys.stderr.write(msg)
        return 1
    python_prefix = sys.argv[1]
    python_version = sys.argv[2]
    path = '%s/lib/python%s' % (python_prefix, python_version)
    path = os.path.normpath(path)
    if path[-1] != '/':
        path = path + '/'
    prefix = None
    for p in sys.path:
        if p.startswith(path):
            prefix = python_prefix
            break
    if not prefix:
        prefix = site.PREFIXES[-1]
    sys.stdout.write('%s\n' % prefix)
    return 0

if __name__ == '__main__':
    sys.exit(main())
