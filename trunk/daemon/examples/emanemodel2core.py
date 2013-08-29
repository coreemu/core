#!/usr/bin/env python
#
# CORE
# Copyright (c) 2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
emanemodel2core.py: scans an EMANE model source file 
 (e.g. emane/models/rfpipe/maclayer/rfpipemaclayer.cc) and outputs Python
 bindings that allow the model to be used in CORE.

 When using this conversion utility, you should replace XYZ, Xyz, and xyz with
 the actual model name. Note the capitalization convention.
'''

import os, sys, optparse

MODEL_TEMPLATE_PART1 = """
#
# CORE
# Copyright (c)2013 Company.
# See the LICENSE file included in this distribution.
#
# author: Name <email@company.com>
#
'''
xyz.py: EMANE XYZ model bindings for CORE
'''

from core.api import coreapi
from emane import EmaneModel
from universal import EmaneUniversalModel

class EmaneXyzModel(EmaneModel):
    def __init__(self, session, objid = None, verbose = False):
        EmaneModel.__init__(self, session, objid, verbose)

    # model name
    _name = "emane_xyz"
    # MAC parameters
    _confmatrix_mac = [
"""

MODEL_TEMPLATE_PART2 = """
    ]

    # PHY parameters from Universal PHY
    _confmatrix_phy = EmaneUniversalModel._confmatrix 

    _confmatrix = _confmatrix_mac + _confmatrix_phy

    # value groupings
    _confgroups = "XYZ MAC Parameters:1-%d|Universal PHY Parameters:%d-%d" \
           % ( len(_confmatrix_mac), len(_confmatrix_mac) + 1, len(_confmatrix))

    def buildnemxmlfiles(self, e, ifc):
        ''' Build the necessary nem, mac, and phy XMLs in the given path.
            If an individual NEM has a nonstandard config, we need to build
            that file also. Otherwise the WLAN-wide nXXemane_xyznem.xml,
            nXXemane_xyzmac.xml, nXXemane_xyzphy.xml are used.
        '''
        values = e.getifcconfig(self.objid, self._name,
                                self.getdefaultvalues(), ifc)
        if values is None:
            return
        nemdoc = e.xmldoc("nem")
        nem = nemdoc.getElementsByTagName("nem").pop()
        nem.setAttribute("name", "XYZ NEM")
        mactag = nemdoc.createElement("mac")
        mactag.setAttribute("definition", self.macxmlname(ifc))
        nem.appendChild(mactag)
        phytag = nemdoc.createElement("phy")
        phytag.setAttribute("definition", self.phyxmlname(ifc))
        nem.appendChild(phytag)
        e.xmlwrite(nemdoc, self.nemxmlname(ifc))

        names = list(self.getnames())
        macnames = names[:len(self._confmatrix_mac)]
        phynames = names[len(self._confmatrix_mac):]
        # make any changes to the mac/phy names here to e.g. exclude them from
        # the XML output

        macdoc = e.xmldoc("mac")
        mac = macdoc.getElementsByTagName("mac").pop()
        mac.setAttribute("name", "XYZ MAC")
        mac.setAttribute("library", "xyzmaclayer")
        # append MAC options to macdoc
        map( lambda n: mac.appendChild(e.xmlparam(macdoc, n, \
                                       self.valueof(n, values))), macnames)
        e.xmlwrite(macdoc, self.macxmlname(ifc))

        phydoc = EmaneUniversalModel.getphydoc(e, self, values, phynames)
        e.xmlwrite(phydoc, self.phyxmlname(ifc))

"""

def emane_model_source_to_core(infile, outfile):
    do_parse_line = False
    output = MODEL_TEMPLATE_PART1

    with open(infile, 'r') as f:
        for line in f:
            # begin marker
            if "EMANE::ConfigurationDefinition" in line:
                do_parse_line = True
            # end marker -- all done
            if "{0, 0, 0, 0, 0, 0" in line:
                break
            if do_parse_line:
                outstr = convert_line(line)
                if outstr is not None:
                    output += outstr
                continue
    output += MODEL_TEMPLATE_PART2

    if outfile == sys.stdout:
        sys.stdout.write(output)
    else:
        with open(outfile, 'w') as f:
            f.write(output)

def convert_line(line):
    line = line.strip()
    # skip comments
    if line.startswith(('/*', '//')):
        return None
    items = line.strip('{},').split(',')
    if len(items) != 7:
        #print "continuning on line=", len(items), items
        return None
    return convert_items_to_line(items)

def convert_items_to_line(items):
    fields = ('required', 'default', 'count', 'name', 'value', 'type',
              'description')
    getfield = lambda(x): items[fields.index(x)].strip()

    output = "        ("
    output += "%s, " % getfield('name')
    value = getfield('value')
    if value == '"off"':
        type = "coreapi.CONF_DATA_TYPE_BOOL"
        value = "0"
        defaults = '"On,Off"'
    elif value == '"on"':
        type = "coreapi.CONF_DATA_TYPE_BOOL"
        value = '"1"'
        defaults = '"On,Off"'
    else:
        type = "coreapi.CONF_DATA_TYPE_STRING"
        defaults = '""'
    output += "%s, %s, %s, " % (type, value, defaults)
    output += getfield('description')
    output += "),\n"
    return output


def main():
    usagestr = "usage: %prog [-h] [options] -- <command> ..."
    parser = optparse.OptionParser(usage = usagestr)
    parser.set_defaults(infile = None, outfile = sys.stdout)

    parser.add_option("-i", "--infile", dest = "infile",
                      help = "file to read (usually '*mac.cc')")
    parser.add_option("-o", "--outfile", dest = "outfile",
                      help = "file to write (stdout is default)")

    def usage(msg = None, err = 0):
        sys.stdout.write("\n")
        if msg:
            sys.stdout.write(msg + "\n\n")
        parser.print_help()
        sys.exit(err)

    # parse command line options
    (options, args) = parser.parse_args()

    if options.infile is None:
        usage("please specify input file with the '-i' option", err=1)

    emane_model_source_to_core(options.infile, options.outfile)


if __name__ == "__main__":
    main()
