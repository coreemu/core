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
from urlparse import urlparse
import socket

class Sdt(object):
    ''' Helper class for exporting session objects to NRL's SDT3D.
    The connect() method initializes the display, and can be invoked
    when a node position or link has changed.
    '''
    DEFAULT_SDT_URL = "tcp://127.0.0.1:50000/"
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

    class Bunch:
        ''' Helper class for recording a collection of attributes.
        '''
        def __init__(self, **kwds):
            self.__dict__.update(kwds)
    
    def __init__(self, session):
        self.session = session
        self.sock = None
        self.connected = False
        self.showerror = True
        self.url = self.DEFAULT_SDT_URL
        self.verbose = self.session.getcfgitembool('verbose', False)
        # node information for remote nodes not in session._objs
        # local nodes also appear here since their obj may not exist yet
        self.remotes = {}
        session.broker.handlers += (self.handledistributed, )
        
    def is_enabled(self):
        ''' Check for 'enablesdt' session option. Return False by default if
            the option is missing.
        '''
        if not hasattr(self.session.options, 'enablesdt'):
            return False
        enabled = self.session.options.enablesdt
        if enabled in ('1', 'true', 1, True):
            return True
        return False

    def seturl(self):
        ''' Read 'sdturl' from session options, or use the default value.
            Set self.url, self.address, self.protocol
        '''
        url = None
        if hasattr(self.session.options,'sdturl'):
            if self.session.options.sdturl != "":
                url = self.session.options.sdturl
        if url is None or url == "":
            url = self.DEFAULT_SDT_URL
        self.url = urlparse(url)
        self.address = (self.url.hostname, self.url.port)
        self.protocol = self.url.scheme

    def connect(self, flags=0):
        ''' Connect to the SDT address/port if enabled.
        '''
        if not self.is_enabled():
            return False
        if self.connected:
            return True
        if self.session.getstate() == coreapi.CORE_EVENT_SHUTDOWN_STATE:
            return False

        self.seturl()
        if self.showerror:
            self.session.info("connecting to SDT at %s://%s" \
                                  % (self.protocol, self.address))
        if self.sock is None:
            try:
                if (self.protocol.lower() == 'udp'):
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    self.sock.connect(self.address)
                else:
                    # Default to tcp
                    self.sock = socket.create_connection(self.address, 5)
            except Exception, e:
                if self.showerror:
                    self.session.warn("SDT socket connect error: %s" % e)
                self.showerror = False
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
        self.cmd('clear all')
        self.disconnect()
        self.showerror = True
        
    def cmd(self, cmdstr):
        ''' Send an SDT command over a UDP socket. socket.sendall() is used
            as opposed to socket.sendto() because an exception is raised when
            there is no socket listener.
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
            self.sock = None
            self.connected = False
            return False
        
    def updatenode(self, nodenum, flags, x, y, z,
                         name=None, type=None, icon=None):
        ''' Node is updated from a Node Message or mobility script.
        '''
        if not self.connect():
            return
        if flags & coreapi.CORE_API_DEL_FLAG:
            self.cmd('delete node,%d' % nodenum)
            return
        if x is None or y is None:
            return
        (lat, long, alt) = self.session.location.getgeo(x, y, z)
        pos = "pos %.6f,%.6f,%.6f" % (long, lat, alt)
        if flags & coreapi.CORE_API_ADD_FLAG:
            if icon is not None:
                type = name
                icon = icon.replace("$CORE_DATA_DIR", CORE_DATA_DIR)
                icon = icon.replace("$CORE_CONF_DIR", CORE_CONF_DIR)
                self.cmd('sprite %s image %s' % (type, icon))
            self.cmd('node %d type %s label on,"%s" %s' % \
                     (nodenum, type, name, pos))
        else:
            self.cmd('node %d %s' % (nodenum, pos))

    def updatenodegeo(self, nodenum, lat, long, alt):
        ''' Node is updated upon receiving an EMANE Location Event.
            TODO: received Node Message with lat/long/alt.
        '''
        if not self.connect():
            return
        pos = "pos %.6f,%.6f,%.6f" % (long, lat, alt)
        self.cmd('node %d %s' % (nodenum, pos))
        
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
                attr = " line green,2"
            else:
                attr = " line red,2"
            self.cmd('link %s,%s%s' % (node1num, node2num, attr))
    
    def sendobjs(self):
        ''' Session has already started, and the SDT3D GUI later connects.
            Send all node and link objects for display. Otherwise, nodes and
            links will only be drawn when they have been updated (e.g. moved).
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
                self.updatenode(obj.objid, coreapi.CORE_API_ADD_FLAG, x, y, z,
                                obj.name, obj.type, obj.icon)
            for nodenum in sorted(self.remotes.keys()):
                r = self.remotes[nodenum]
                (x, y, z) = r.pos
                self.updatenode(nodenum, coreapi.CORE_API_ADD_FLAG, x, y, z,
                                r.name, r.type, r.icon)

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
            for n1num in sorted(self.remotes.keys()):
                r = self.remotes[n1num]
                for (n2num, wl) in r.links:
                    self.updatelink(n1num, n2num, coreapi.CORE_API_ADD_FLAG, wl)
    
    def handledistributed(self, msg):
        ''' Broker handler for processing CORE API messages as they are 
            received. This is used to snoop the Node messages and update
            node positions.
        '''
        if msg.msgtype == coreapi.CORE_API_LINK_MSG:
            return self.handlelinkmsg(msg)
        elif msg.msgtype == coreapi.CORE_API_NODE_MSG:
            return self.handlenodemsg(msg)
            
    def handlenodemsg(self, msg):
        ''' Process a Node Message to add/delete or move a node on
            the SDT display. Node properties are found in session._objs or
            self.remotes for remote nodes (or those not yet instantiated).
        '''
        # for distributed sessions to work properly, the SDT option should be
        # enabled prior to starting the session
        if not self.is_enabled():
            return False
        # node.(objid, type, icon, name) are used.
        nodenum = msg.gettlv(coreapi.CORE_TLV_NODE_NUMBER)
        if not nodenum:
            return
        x = msg.gettlv(coreapi.CORE_TLV_NODE_XPOS)
        y = msg.gettlv(coreapi.CORE_TLV_NODE_YPOS)
        z = None
        name = msg.gettlv(coreapi.CORE_TLV_NODE_NAME)
        
        nodetype = msg.gettlv(coreapi.CORE_TLV_NODE_TYPE)
        model = msg.gettlv(coreapi.CORE_TLV_NODE_MODEL)
        icon = msg.gettlv(coreapi.CORE_TLV_NODE_ICON)

        net = False
        if nodetype == coreapi.CORE_NODE_DEF or \
           nodetype == coreapi.CORE_NODE_PHYS or \
           nodetype == coreapi.CORE_NODE_XEN:
            if model is None:
                model = "router"
            type = model
        elif nodetype != None:
            type = coreapi.node_class(nodetype).type
            net = True
        else:
            type = None
            
        try:
            node = self.session.obj(nodenum)
        except KeyError:
            node = None
        if node:
            self.updatenode(node.objid, msg.flags, x, y, z,
                            node.name, node.type, node.icon)
        else:
            if nodenum in self.remotes:
                remote = self.remotes[nodenum]
                if name is None:
                    name = remote.name
                if type is None:
                    type = remote.type
                if icon is None:
                    icon = remote.icon
            else:
                remote = self.Bunch(objid=nodenum, type=type, icon=icon,
                                    name=name, net=net, links=set())
                self.remotes[nodenum] = remote
            remote.pos = (x, y, z)
            self.updatenode(nodenum, msg.flags, x, y, z, name, type, icon)
        
    def handlelinkmsg(self, msg):
        ''' Process a Link Message to add/remove links on the SDT display.
            Links are recorded in the remotes[nodenum1].links set for updating
            the SDT display at a later time.
        '''
        if not self.is_enabled():
            return False
        nodenum1 = msg.gettlv(coreapi.CORE_TLV_LINK_N1NUMBER)
        nodenum2 = msg.gettlv(coreapi.CORE_TLV_LINK_N2NUMBER)
        link_msg_type = msg.gettlv(coreapi.CORE_TLV_LINK_TYPE)
        # this filters out links to WLAN and EMANE nodes which are not drawn
        if self.wlancheck(nodenum1):
            return
        wl = (link_msg_type == coreapi.CORE_LINK_WIRELESS)
        if nodenum1 in self.remotes:
            r = self.remotes[nodenum1]
            if msg.flags & coreapi.CORE_API_DEL_FLAG:
                if (nodenum2, wl) in r.links:
                    r.links.remove((nodenum2, wl))
            else:
                r.links.add((nodenum2, wl))
        self.updatelink(nodenum1, nodenum2, msg.flags, wireless=wl)

    def wlancheck(self, nodenum):
        ''' Helper returns True if a node number corresponds to a WlanNode
            or EmaneNode.
        '''
        if nodenum in self.remotes:
            type = self.remotes[nodenum].type
            if type in ("wlan", "emane"):
                return True
        else:
            try:
                n = self.session.obj(nodenum)
            except KeyError:
                return False
            if isinstance(n, (nodes.WlanNode, nodes.EmaneNode)):
                return True
        return False
