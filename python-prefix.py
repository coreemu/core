#!/usr/bin/env python

import sys
import os.path
import site

def main():
    if len(sys.argv) != 2:
        msg = 'usage: %s <prefix>\n' % os.path.basename(sys.argv[0])
        sys.stderr.write(msg)
        return 1
    python_prefix = sys.argv[1]
    prefix = None
    for p in sys.path:
        if python_prefix in p:
            prefix = python_prefix
            break
    if not prefix:
        prefix = site.PREFIXES[-1]
    print prefix
    return 0

if __name__ == '__main__':
    sys.exit(main())
