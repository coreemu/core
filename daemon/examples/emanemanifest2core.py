#!/usr/bin/env python

from emanesh import manifest
import os.path
import re
import textwrap

class EmaneManifest2Model(object):

    class EmaneModel(object):

        class EmaneModelParameter(object):

            intfloat_regex = re.compile(r'^([0-9]+)\.(0*)$')
            indent = ' ' * 16

            def __init__(self, name, apitype, default, caption,
                         possible_values = ()):
                self.name = name
                self.apitype = apitype
                self.default = self.intfloat_regex.sub(r'\1.0', default)
                self.possible_values = possible_values
                self.caption = caption

            def __str__(self):
                return '''%s('%s', %s,\n%s '%s', '%s', '%s')''' % \
                    (self.indent, self.name, self.apitype,
                     self.indent, self.default,
                     ','.join(self.possible_values), self.caption)

        def __init__(self, name):
            self.name = name
            self.parameters = []

        def add_parameter(self, name, apitype, default, caption,
                          possible_values = ()):
            p = self.EmaneModelParameter(name, apitype, default, caption,
                                         possible_values)
            self.parameters.append(p)

    mac_xml_path = '/usr/share/emane/xml/models/mac'

    # map emane parameter types to CORE api data types
    core_api_type = {
        'uint8': 'coreapi.CONF_DATA_TYPE_UINT8',
        'uint16': 'coreapi.CONF_DATA_TYPE_UINT16',
        'uint32': 'coreapi.CONF_DATA_TYPE_UINT32',
        'uint64': 'coreapi.CONF_DATA_TYPE_UINT64',
        'int8': 'coreapi.CONF_DATA_TYPE_INT8',
        'int16': 'coreapi.CONF_DATA_TYPE_INT16',
        'int32': 'coreapi.CONF_DATA_TYPE_INT32',
        'int64': 'coreapi.CONF_DATA_TYPE_INT64',
        'float': 'coreapi.CONF_DATA_TYPE_FLOAT',
        'double': 'coreapi.CONF_DATA_TYPE_FLOAT',
        'bool': 'coreapi.CONF_DATA_TYPE_BOOL',
        'string': 'coreapi.CONF_DATA_TYPE_STRING',
    }

    parameter_regex = re.compile(r'^\^\(([\|\-\w]+)\)\$$')

    @classmethod
    def emane_model(cls, xmlfile):
        m = manifest.Manifest(xmlfile)
        model = cls.EmaneModel(m.getName())
        for name in m.getAllConfiguration():
            info = m.getConfigurationInfo(name)
            apitype = None
            for t in 'numeric', 'nonnumeric':
                if t in info:
                    apitype = cls.core_api_type[info[t]['type']]
                    break
            default = ''
            if info['default']:
                values = info['values']
                if values:
                    default = values[0]
            caption = name
            possible_values = []
            if apitype == 'coreapi.CONF_DATA_TYPE_BOOL':
                possible_values = ['On,Off']
            elif apitype == 'coreapi.CONF_DATA_TYPE_STRING':
                if name == 'pcrcurveuri':
                    default = os.path.join(cls.mac_xml_path,
                                           model.name, model.name + 'pcr.xml')
                else:
                    regex = info['regex']
                    if regex:
                        match = cls.parameter_regex.match(regex)
                        if match:
                            possible_values = match.group(1).split('|')
            model.add_parameter(name, apitype, default,
                                caption, possible_values)
        model.parameters.sort(key = lambda x: x.name)
        return model

    @classmethod
    def core_emane_model(cls, class_name, macmanifest_filename,
                         phymanifest_filename):
        template = '''\
        from core.emane.emane import EmaneModel
        from core.api import coreapi

        class BaseEmaneModel(EmaneModel):
            def __init__(self, session, objid = None, verbose = False):
                EmaneModel.__init__(self, session, objid, verbose)

            def buildnemxmlfiles(self, e, ifc):
                \'\'\'\\
                Build the necessary nem, mac, and phy XMLs in the given path.
                If an individual NEM has a nonstandard config, we need to
                build that file also. Otherwise the WLAN-wide
                nXXemane_*nem.xml, nXXemane_*mac.xml, nXXemane_*phy.xml are
                used.
                \'\'\'
                values = e.getifcconfig(self.objid, self._name,
                                        self.getdefaultvalues(), ifc)
                if values is None:
                    return

                nemdoc = e.xmldoc('nem')
                nem = nemdoc.getElementsByTagName('nem').pop()
                e.appendtransporttonem(nemdoc, nem, self.objid, ifc)

                def append_definition(tag, name, xmlname, doc):
                    el = doc.createElement(name)
                    el.setAttribute('definition', xmlname)
                    tag.appendChild(el)

                append_definition(nem, 'mac', self.macxmlname(ifc), nemdoc)
                append_definition(nem, 'phy', self.phyxmlname(ifc), nemdoc)

                e.xmlwrite(nemdoc, self.nemxmlname(ifc))

                names = list(self.getnames())

                def append_options(tag, optnames, doc):
                    for name in optnames:
                        value = self.valueof(name, values).strip()
                        if value:
                            tag.appendChild(e.xmlparam(doc, name, value))

                macdoc = e.xmldoc('mac')
                mac = macdoc.getElementsByTagName('mac').pop()
                mac.setAttribute('library', '%(modelLibrary)s')
                # append MAC options to macdoc
                append_options(mac, names[:len(self._confmatrix_mac)], macdoc)
                e.xmlwrite(macdoc, self.macxmlname(ifc))

                phydoc = e.xmldoc('phy')
                phy = phydoc.getElementsByTagName('phy').pop()
                # append PHY options to phydoc
                append_options(phy, names[len(self._confmatrix_mac):], phydoc)
                e.xmlwrite(phydoc, self.phyxmlname(ifc))

        class %(modelClass)s(BaseEmaneModel):
            # model name
            _name = 'emane_%(modelName)s'

            # configuration parameters are
            #  ( 'name', 'type', 'default', 'possible-value-list', 'caption')
            # MAC parameters
            _confmatrix_mac = [\n%(confMatrixMac)s
            ]

            # PHY parameters
            _confmatrix_phy = [\n%(confMatrixPhy)s
            ]

            _confmatrix = _confmatrix_mac + _confmatrix_phy

            # value groupings
            _confgroups = 'MAC Parameters:1-%%s|PHY Parameters:%%s-%%s' %% \\
                          (len(_confmatrix_mac), \\
                           len(_confmatrix_mac) + 1, len(_confmatrix))
        '''
        macmodel = cls.emane_model(macmanifest_filename)
        phymodel = cls.emane_model(phymanifest_filename)
        d = {
            'modelClass': 'Emane%sModel' % (class_name),
            'modelName': macmodel.name,
            'confMatrixMac': ',\n'.join(map(str, macmodel.parameters)) + ',',
            'confMatrixPhy': ',\n'.join(map(str, phymodel.parameters)) + ',',
            'modelLibrary': macmodel.name,
         }
        return textwrap.dedent(template % d)

def main():
    import argparse
    import sys
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description = 'Create skeleton CORE bindings from ' \
            'EMANE model manifest files.',
        epilog = 'example:\n' \
            '    %(prog)s -c RadioX \\\n' \
            '        -m /usr/share/emane/manifest/radiox.xml \\\n' \
            '        -p /usr/share/emane/manifest/emanephy.xml')
    parser.add_argument('-c', '--class-name', dest = 'classname',
                        required = True, help = 'corresponding python '
                        'class name: RadioX -> EmaneRadioXModel')
    parser.add_argument('-m', '--mac-xmlfile', dest = 'macxmlfilename',
                        required = True,
                        help = 'MAC model manifest XML filename')
    parser.add_argument('-p', '--phy-xmlfile', dest = 'phyxmlfilename',
                        required = True,
                        help = 'PHY model manifest XML filename')
    args = parser.parse_args()
    model = EmaneManifest2Model.core_emane_model(args.classname,
                                                 args.macxmlfilename,
                                                 args.phyxmlfilename)
    sys.stdout.write(model)

if __name__ == "__main__":
    main()
