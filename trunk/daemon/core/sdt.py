#
# CORE
# Copyright (c)2012-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
sdt.py: Scripted Display Tool (SDT3D) helper
'''

from core.constants import *
from core.api import coreapi
from coreobj import PyCoreNet, PyCoreObj
from core.netns import nodes
import socket

class Sdt(object):
    ''' Helper class for exporting session objects to NRL's SDT3D.
    The connect() method initializes the display, and can be invoked
    when a node position or link has changed.
    '''
    DEFAULT_SDT_PORT = 5000
    # default altitude (in meters) for flyto view
    DEFAULT_ALT = 2500
    # TODO: read in user's nodes.conf here; below are default node types
    #       from the GUI
    DEFAULT_SPRITES = [('router', 'router.gif'), ('host', 'host.gif'),
                       ('PC', 'pc.gif'), ('mdr', 'mdr.gif'),
                       ('prouter', 'router_green.gif'), ('xen', 'xen.gif'),
                       ('hub', 'hub.gif'), ('lanswitch','lanswitch.gif'), 
                       ('wlan', 'wlan.gif'), ('rj45','rj45.gif'), 
                       ('tunnel','tunnel.gif'),
                       ]
    
    def __init__(self, session):
        self.session = session
        self.sock = None
        self.connected = False
        self.showerror = True
        self.verbose = self.session.getcfgitembool('verbose', False)
        self.address = ("127.0.0.1", self.DEFAULT_SDT_PORT)
        
    def is_enabled(self):
        if not hasattr(self.session.options, 'enablesdt'):
            return False
        if self.session.options.enablesdt == '1':
            return True
        return False

    def connect(self, flags=0):
        if not self.is_enabled():
            return False
        if self.connected:
            return True
        if self.showerror:
            self.session.info("connecting to SDT at %s:%s" % self.address)
        if self.sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.connect(self.address)
        except Exception, e:
            self.session.warn("SDT socket connect error: %s" % e)
            return False
        if not self.initialize():
            return False
        self.connected = True
        # refresh all objects in SDT3D when connecting after session start
        if not flags & coreapi.CORE_API_ADD_FLAG:
            if not self.sendobjs():
                return False
        return True
    
    def initialize(self):
        ''' Load icon sprites, and fly to the reference point location on
        the virtual globe.
        '''
        if not self.cmd('path "%s/icons/normal"' % CORE_DATA_DIR):
            return False
        # send node type to icon mappings
        for (type, icon) in self.DEFAULT_SPRITES:
            if not self.cmd('sprite %s image %s' % (type, icon)):
                return False
        (lat, long) = self.session.location.refgeo[:2]
        return self.cmd('flyto %.6f,%.6f,%d' % (long, lat, self.DEFAULT_ALT))
    
    def disconnect(self):
        try:
            self.sock.close()
        except:
            pass
        self.sock = None
        self.connected = False
        
    def shutdown(self):
        ''' Invoked from Session.shutdown() and Session.checkshutdown().
        '''
        # TODO: clear SDT display here?
        self.disconnect()
        self.showerror = True
        
    def cmd(self, cmdstr):
        ''' Send an SDT command over a UDP socket. socket.sendall() is used
        as opposed to socket.sendto() because an exception is raised when there
        is no socket listener.
        '''
        if self.sock is None:
            return False
        try:
            if self.verbose:
                self.session.info("sdt: %s" % cmdstr)
            self.sock.sendall("%s\n" % cmdstr)
            return True
        except Exception, e:
            if self.showerror:
                self.session.warn("SDT connection error: %s" % e)
                self.showerror = False
            self.connected = False
            return False
        
    def updatenode(self, node, flags, x, y, z):
        ''' Node is updated from a Node Message or mobility script.
        '''
        if node is None:
            return
        if not self.connect():
            return
        if flags & coreapi.CORE_API_DEL_FLAG:
            self.cmd('delete node,%d' % node.objid)
            return
        (lat, long, alt) = self.session.location.getgeo(x, y, z)
        pos = "pos %.6f,%.6f,%.6f" % (long, lat, alt)
        if flags & coreapi.CORE_API_ADD_FLAG:
            type = node.type
            if node.icon is not None:
                type = node.name
                self.cmd('sprite %s image %s' % (type, node.icon))
            self.cmd('node %d type %s label on,"%s" %s' % \
                     (node.objid, type, node.name, pos))
        else:
            self.cmd('node %d %s' % (node.objid, pos))
            
    def updatenodegeo(self, node, lat, long, alt):
        ''' Node is updated upon receiving an EMANE Location Event.
        '''
        if node is None:
            return
        if not self.connect():
            return
        pos = "pos %.6f,%.6f,%.6f" % (long, lat, alt)
        self.cmd('node %d %s' % (node.objid, pos))
        
    def updatelink(self, node1num, node2num, flags, wireless=False):
        ''' Link is updated from a Link Message or by a wireless model.
        '''
        if node1num is None or node2num is None:
            return
        if not self.connect():
            return
        if flags & coreapi.CORE_API_DEL_FLAG:
            self.cmd('delete link,%s,%s' % (node1num, node2num))
        elif flags & coreapi.CORE_API_ADD_FLAG:
            attr = ""
            if wireless:
                attr = " line green"
            self.cmd('link %s,%s%s' % (node1num, node2num, attr))
    
    def sendobjs(self):
        ''' Session has already started, and the SDT3D GUI later connects.
        Send all node and link objects for display. Otherwise, nodes and links
        will only be drawn when they have been updated.
        '''
        nets = []
        with self.session._objslock:
            for obj in self.session.objs():
                if isinstance(obj, PyCoreNet):
                    nets.append(obj)
                if not isinstance(obj, PyCoreObj):
                    continue
                (x, y, z) = obj.getposition()
                if x is None or y is None:
                    continue
                self.updatenode(obj, coreapi.CORE_API_ADD_FLAG, x, y, z)
            for net in nets:
                # use tolinkmsgs() to handle various types of links
                msgs = net.tolinkmsgs(flags = coreapi.CORE_API_ADD_FLAG)
                for msg in msgs:
                    msghdr = msg[:coreapi.CoreMessage.hdrsiz]
                    flags = coreapi.CoreMessage.unpackhdr(msghdr)[1]
                    m = coreapi.CoreLinkMessage(flags, msghdr,
                                               msg[coreapi.CoreMessage.hdrsiz:])
                    n1num = m.gettlv(coreapi.CORE_TLV_LINK_N1NUMBER)
                    n2num = m.gettlv(coreapi.CORE_TLV_LINK_N2NUMBER)
                    link_msg_type = m.gettlv(coreapi.CORE_TLV_LINK_TYPE)
                    if isinstance(net, nodes.WlanNode) or \
                       isinstance(net, nodes.EmaneNode):
                        if (n1num == net.objid):
                            continue
                    wl = (link_msg_type == coreapi.CORE_LINK_WIRELESS)   
                    self.updatelink(n1num, n2num, coreapi.CORE_API_ADD_FLAG, wl)
                    

