#
# CORE
# Copyright (c)2016 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Rod Santiago
#          John Kharouta
#



import threading, traceback, sys
from core.api import coreapi, corewrapper, coreapi2
from core.experiments import ExperimentStore

# Aliases
wrapper = corewrapper
legacy = coreapi

# Legacy node types that are Devices in API2
deviceTypesSet = set([
    coreapi.CORE_NODE_SWITCH,
    coreapi.CORE_NODE_HUB,
    coreapi.CORE_NODE_WLAN,
    coreapi.CORE_NODE_RJ45,
    coreapi.CORE_NODE_TUNNEL,
    coreapi.CORE_NODE_KTUNNEL,
    coreapi.CORE_NODE_EMANE])

# Legacy node types that are Devices in API2
nodeTypesSet = set([
    coreapi.CORE_NODE_DEF,
    coreapi.CORE_NODE_XEN])



# Legacy node types to API2 device type field mapping
devtypeDict = {
    coreapi.CORE_NODE_SWITCH: coreapi2.Device.SWITCH,
    coreapi.CORE_NODE_HUB: coreapi2.Device.HUB,
    coreapi.CORE_NODE_WLAN: coreapi2.Device.WLAN,
    coreapi.CORE_NODE_RJ45: coreapi2.Device.RJ45,
    coreapi.CORE_NODE_TUNNEL: coreapi2.Device.TUNNEL,
    coreapi.CORE_NODE_KTUNNEL: coreapi2.Device.KTUNNEL
}

# Legacy node types to API2 emulator field mapping
emulationDict = {
    coreapi.CORE_NODE_DEF: coreapi2.Node.DEFAULT,
    coreapi.CORE_NODE_XEN: coreapi2.Node.XEN,
    coreapi.CORE_NODE_EMANE: coreapi2.Device.EMANE
 }




class CoreApiBridge(object):

    def __init__(self, handler):
        # The collector is used for gathering node messages sent by the core session, 
        # for example, during INSTANTIATION as nodes are started until RUNTIME.
        self.collector = None

        # The currently associated (added or joined) experiment
        self.assocExperiment = None

        # Mutex
        self.lock = threading.Lock()

        # Reference to the owning handler in the core-daemon
        self.handler = handler

    def info(self, msg):
        ''' Utility method for writing output to stdout.
        '''
        print msg
        sys.stdout.flush()

    def warn(self, msg):
        ''' Utility method for writing output to stderr.
        '''
        print >> sys.stderr, msg
        sys.stderr.flush()

    def recvmsg(self):
        ''' Receive data, parse a CoreMessage and queue it onto an existing
        session handler's queue, if available.
        '''

        data = coreapi2.recvAndUnpack(self.handler.request.recv)
        msgs = self.processApi2Message(data)

        return msgs

    def dispatchreplies(self, replies):
        ''' Dispatch a reply to a previously received message.
        '''
        api2Replies = self.processLegacyCoreMessage(replies)
        if api2Replies:
            for reply in api2Replies:
                try:
                    # send to API2 client 
                    self.handler.request.sendall(reply)
                except Exception, e:
                    if self.handler.debug:
                        self.info("-"*60)
                        traceback.print_exc(file=sys.stdout)
                        self.info("-"*60)
                    raise e


    def sendall(self, data):
        ''' The daemon calls this method with legacy API data. Convert first
        API2 then send.
        '''

        try:
            msgs = self.processLegacyCoreMessage((data,))
            if msgs:
                for msg in msgs:
                    self.handler.request.sendall(msg)
        except Exception, e:
            if self.handler.debug:
                self.info("-"*60)
                traceback.print_exc(file=sys.stdout)
                self.info("-"*60)
            raise e





    def processApi2Message(self, data):
        message = coreapi2.CoreMessage()
        message.ParseFromString(data)
        if message.HasField('session'):
            return self.processApi2SessionMsg(message.session,
                                              message.purpose)
        if message.HasField('experiment'):
            return self.processApi2ExperimentMsg(message.experiment, 
                                                 message.purpose)
        if message.HasField('event'):
            return self.processApi2Event(message.event, 
                                         message.purpose)
            

    def processLegacyCoreMessage(self, messages):
        api2msgs = []
        for msgstr in messages:
            # Unpack the message
            parser = wrapper.CoreMessageParser(msgstr)
            if parser.getType() == legacy.CORE_API_REG_MSG:
                self.processLegacyRegMsg(parser.createWrapper(), api2msgs)

            elif parser.getType() == legacy.CORE_API_SESS_MSG:
                self.processLegacySessionMsg(parser.createWrapper(), api2msgs)

            elif parser.getType() == legacy.CORE_API_EVENT_MSG:
                self.processLegacyEventMsg(parser.createWrapper(), api2msgs)

            elif parser.getType() == legacy.CORE_API_NODE_MSG:
                self.processLegacyNodeMsg(parser.createWrapper(), api2msgs)
            else:
                self.warn("received message type %s" % (parser.getType()))
        return api2msgs







    def processLegacyRegMsg(self, regMsg, api2msgs):
        '''
        Intercept an outgoing register message from the CORE daemon and generate
        equivalent API2 message to send to the client
        '''

        '''
        print "RegisterMessage"
        print "\twireless=", regMsg.getWireless()
        print "\tmobility=", regMsg.getMobility()
        print "\tutility=", regMsg.getUtility()
        print "\texec=",  regMsg.getExecsrv()
        print "\tgui=", regMsg.getGui()
        print "\temul=", regMsg.getEmulsrv()
        print "\tsess=", regMsg.getSession()
        '''
        pass

    def processLegacySessionMsg(self, sessMsg, api2msgs):
        '''
        Intercept an outgoing session message from the CORE daemon and generate the equivalent
        API2 messages to send to the client
        '''

        '''
        print "SessionMessage"
        print "\tnumber=",  sessMsg.getNumber()
        print "\tname=",  sessMsg.getName()
        print "\tfile=",  sessMsg.getFile()
        print "\tnodecount=",  sessMsg.getNodecount()
        print "\tdate=",  sessMsg.getDate()
        print "\tthumb=",  sessMsg.getThumb()
        print "\tuser=",  sessMsg.getUser()
        print "\topaque=",  sessMsg.getOpaque()
        '''
        sessions = sessMsg.getNumber().split("|")
        port_num = int(sessions[0])
        newMsg = coreapi2.CoreMessage()
        newMsg.session.clientId = 'client' + sessions[0]
        newMsg.session.port_num = port_num
        
        # List active experiments in the server
        for sid in sessions:
            sid = int(sid)
            if sid == 0:
                continue
            session = self.handler.session.server.getsession(sessionid=sid, useexisting=True)
            if session is None:
                self.warn("Invalid session ID received from daemon")
                continue
            if session == self.handler.session:
                continue
            expId =  session.metadata.getitem('experimentId')
            if expId:
                newMsg.session.all_exps.append(expId)
            else:
                newMsg.session.all_exps.append('_%s' % (str(sid)))

        newMsg.purpose = coreapi2.ADD
        api2msgs.append(coreapi2.pack(newMsg))

    def processLegacyEventMsg(self, event, api2msgs):
        '''
        Intercept an outgoing event generated by the CORE daemon and generate the equivalent
        API2 messages to send to the client
        '''

        '''
        print "Event:"
        print "\tnode=", event.getNode()
        print "\ttype=", event.getType()
        print "\tname=", event.getName()
        print "\tdata=", event.getData()
        print "\ttime=", event.getTime()
        print "\tsessions=", event.getSession()
        '''

        if event.getType() == legacy.CORE_EVENT_RUNTIME_STATE:
            newMsg = coreapi2.CoreMessage()
            newMsg.purpose = coreapi2.STATE_CHANGE
            newMsg.event.state = coreapi2.RUNTIME
            api2msgs.append(coreapi2.pack(newMsg))
            with self.lock:
                if self.collector:
                    self.collector.experiment.running = True
                    self.collector.purpose = coreapi2.MODIFY
                else:
                    raise RuntimeError, "runtime entered without an instantiated experiment"
                api2msgs.append(coreapi2.pack(self.collector))
                self.collector = None
    
    def processLegacyNodeMsg(self, nodeMsg, api2msgs):
        '''
        Intercept an outgoing legacy node message generated by the CORE daemon and generate the equivalent
        API2 messages to send to the client
        '''

        print "Node:"
        print "\tnumber=", nodeMsg.getNumber()
        print "\ttype=", nodeMsg.getType()
        print "\tname=", nodeMsg.getName()
        print "\tipaddr=", nodeMsg.getIpaddr()
        print "\tmacaddr=", nodeMsg.getMacaddr()
        print "\tip6addr=", nodeMsg.getIp6addr()
        print "\tmodel=", nodeMsg.getModel()
        print "\temusrv=", nodeMsg.getEmusrv()
        print "\tsession=", nodeMsg.getSession()
        print "\txpos=", nodeMsg.getXpos()
        print "\typos=", nodeMsg.getYpos()
        print "\tcanvas=", nodeMsg.getCanvas()
        print "\temuid=", nodeMsg.getEmuid()
        print "\tnetid=", nodeMsg.getNetid()
        print "\tservices=", nodeMsg.getServices()
        print "\tlat=", nodeMsg.getLat()
        print "\tlon=", nodeMsg.getLong()
        print "\talt=", nodeMsg.getAlt()
        print "\ticon=", nodeMsg.getIcon()
        print "\topaque=", nodeMsg.getOpaque()

        api2_node=None
        api2_dev=None
        with self.lock:
            #if self.assocExperiment:
            nodeOrDev = None
            newMsg = None
            if not self.collector:
                newMsg = coreapi2.CoreMessage()

            # The legacy API uses a Node message to convey everything from hubs to hosts. But it does
            # always have type information in it.
            # Check if the legacy message updates an existing API2 node or a device
            isNode = self.assocExperiment and coreapi2.findNodeByIdx(self.assocExperiment, 
                                                                     nodeMsg.getNumber())
            isDev = self.assocExperiment and coreapi2.findDeviceByIdx(self.assocExperiment, 
                                                                      nodeMsg.getNumber())

            # If the node number in the message maps to a node or a device in the associated experiment,
            # check if the message indicates a consistent type
            if isNode and nodeMsg.getType() is not None and nodeMsg.getType() not in nodeTypesSet:
                raise RuntimeError, "Inconsistent node types."
            if isDev and nodeMsg.getType() is not None and nodeMsg.getType() not in deviceTypesSet:
                raise RuntimeError, "Inconsistent device types."
            
            if not isNode and not isDev and nodeMsg.getType() is not None:
                isNode = isNode(nodeMsg.getType())
                isDev = isDev(nodeMsg.getType())
                
            # Add the node/device to either the experiment object in the collector for transmission as
            # part of a API2 session/experiment, or to a new message for independent API2 Node or
            # Device message transmission
            if isNode:
                # add or update an node
                if self.collector:
                    nodeOrDev = coreapi2.getNodeByIdx(self.collector.experiment, nodeMsg.getNumber())
                else:
                    nodeOrDev = newMsg.node
            elif isDev:
                # add or update a device
                if self.collector:
                    nodeOrDev = coreapi2.getDeviceByIdx(self.collector.experiment, nodeMsg.getNumber())
                else:
                    nodeOrDev = newMsg.device
            else:
                raise RuntimeError, "Unrecognized node number without type information"

            if nodeOrDev:
                nodeOrDev.idx = nodeMsg.getNumber()
                if nodeMsg.getEmuid() is not None: nodeOrDev.emu_id=nodeMsg.getEmuid()
                if nodeMsg.getName() is not None:  nodeOrDev.name=nodeMsg.getName()
                if nodeMsg.getXpos() is not None:  nodeOrDev.location.x_pos=nodeMsg.getXpos()
                if nodeMsg.getYpos() is not None:  nodeOrDev.location.y_pos=nodeMsg.getYpos()
                if nodeMsg.getIcon() is not None:  nodeOrDev.icon=nodeMsg.getIcon()
                if nodeMsg.getType() is not None:
                    try:
                        if isDev and devtypeDict.get(nodeMsg.getType()) is not None:
                            nodeOrDev.device_type = devtypeDict.get(nodeMsg.getType())
                        if emulationDict.get(nodeMsg.getType()) is not None:
                            nodeOrDev.emulation = emulationDict.get(nodeMsg.getType())
                    except e:
                        self.warn("Unmapped type in legacy node message")

                # TODO: if nodeMsg.getCanvas() is not None: nodeOrDev.canvas=nodeMsg.getCanvas()
                # TODO: association with networks
                # TODO: services

                if newMsg:
                    newMsg.purpose = coreapi2.MODIFY
                    api2msgs.append(coreapi2.pack(newMsg))
            else:
                self.warn("Received update for unknown node or device %d" % (nodeMsg.getNumber()))
        

    def processApi2SessionMsg(self, message, purpose):
        if purpose == coreapi2.ADD:
            if self.handler.debug:
                self.info('Received ADD session request message')

            legacymsgs = []
            legacymsgs.append(wrapper.RegMsg.instantiate(0, gui='true'))
            return legacymsgs
            # The response will be sent to the API2 client when a legacy session message is received from the daemon
        elif purpose == coreapi2.MODIFY:
            if self.handler.debug:
                self.info('Received MODIFY session request message')

            legacymsgs = []
            if message.HasField("experiment"):
                exp = message.experiment
                if exp.HasField("experimentId"):
                    expId = str(exp.experimentId)
                    response = coreapi2.CoreMessage()
                    response.experiment.experimentId = exp.experimentId;
                    response.purpose = purpose
                    with self.lock:
                        self.assocExperiment = exp
                        self.collector = response
                    if expId.startswith('_'):
                        try:
                            legacySessNo = int(expId[1:])
                            legacymsgs.append(wrapper.ConfMsg.instantiate("all", 
                                                                            coreapi.CONF_TYPE_FLAGS_RESET))
                            legacymsgs.append(wrapper.RegMsg.instantiate(0, gui='true'))
                            legacymsgs.append(wrapper.SessionMsg.instantiate(0, legacySessNo))
                        except:
                            # TODO: get legacy session number from experimentId if running, or pass back
                            # non-running experiment components
                            pass
                    else:
                        # TODO: get legacy session number from experimentId if running, or pass back
                        # non-running experiment components
                        pass
                else:
                    self.warn("session modify request without an experimentId")
            else:
                self.warn("session modify request without an experiment")

            
            return legacymsgs
        elif purpose == coreapi2.DELETE:
            # TODO: shutdown session
            pass
        else:
            self.warn('Received invalid purpose for SESSION')


    def processApi2ExperimentMsg(self, exp, purpose):
        if purpose == coreapi2.ADD:
            if ExperimentStore.addExperiment(exp):
                response = coreapi2.CoreMessage()
                response.experiment.experimentId = exp.experimentId;
                response.purpose = purpose

                # Start a collector for gathering node messages instantiated in the core session
                with self.lock:
                    if not self.collector:
                        self.assocExperiment = exp
                        self.collector = response
                    else:
                        raise RuntimeError, "Instantiation of experiment while another is active"
                self.handler.request.sendall(coreapi2.pack(response))
                return self.translateApi2ExperimentMsg(exp)
            else:
                return self.Api2Error("unable to add experiment")
        elif purpose == coreapi2.MODIFY:
            # Detect if a change in state is requested
            if exp.HasField('running'):
                if exp.running:
                    # TODO: Check for a state transition
                    # transition to instantiation state (legacy)
                    msgs = []
                    msgs.append(wrapper.EventMsg.instantiate(
                        legacy.CORE_EVENT_INSTANTIATION_STATE))
                    return msgs
                else:
                    # TODO: Check for transition from running to not running
                    # transition to data collection state (legacy)
                    msgs = []
                    msgs.append(wrapper.EventMsg.instantiate(
                        legacy.CORE_EVENT_DATACOLLECT_STATE))
                    return msgs
            else:
                self.warn("Unsupported experiment modification received")


    def translateApi2ExperimentMsg(self, message):
        if self.handler.debug:
            self.info('Received experiment message')
        msgs = []
        # Flag need to be 0 otherwise CORE will not enter runtime state (per JavaAdaptor, need verification)
        msgs.append(wrapper.SessionMsg.instantiate(
            0, "0", 
            nodecount=str(len(message.nodes) + len(message.devices))))
        # Quickly transition through the definition and configuration states
        msgs.append(wrapper.EventMsg.instantiate(
            legacy.CORE_EVENT_DEFINITION_STATE))
        msgs.append(wrapper.EventMsg.instantiate(
            legacy.CORE_EVENT_CONFIGURATION_STATE))

        # Send location
        # TODO: Add this info to the Experiment
        msgs.append(wrapper.ConfMsg.instantiate(obj="location",
                                                dataTypes=(9,9,9,9,9,9),
                                                dataValues='0|0| 47.5766974863|-122.125920191|0.0|150.0'))

        # TODO
        # Send control net configuration
        # send node types
        # send services

        # send nodes
        devices = {}
        for node in message.nodes:
            if node.idx in devices:
                raise IOError, "received experiment with node/device duplicates"
            devices[node.idx] = node
            # TODO: Add other fields
            msgs.append(wrapper.NodeMsg.instantiate(
                legacy.CORE_API_ADD_FLAG|legacy.CORE_API_STR_FLAG,
                node.idx,
                str(node.name)))

        for device in message.devices:
            if device.idx in devices:
                raise IOError, "received experiment with node/device duplicates"
            devices[device.idx] = device
            # TODO: Add other fields
            msgs.append(wrapper.NodeMsg.instantiate(
                legacy.CORE_API_ADD_FLAG|legacy.CORE_API_STR_FLAG,
                device.idx,
                str(device.name),
                type = legacy.CORE_NODE_SWITCH)) # TODO: Update this later

        for network in message.networks:
            for channel in network.channels:
                if len(channel.endpoints) == 2:
                    ep0 = channel.endpoints[0]
                    ep1 = channel.endpoints[1]
                    if ep0.dev_idx not in devices or ep1.dev_idx not in devices:
                        raise IOError, "received channel message with invalid first endpoint device (%d)" % (ep0.dev_idx)
                    if ep1.dev_idx not in devices:
                        raise IOError, "received channel message with invalid second endpoint device (%d)" % (ep1.dev_idx)
                    if ep0.intf_idx in devices[ep0.dev_idx].interfaces:
                        raise IOError, "received channel message with invalid first endpoint interface (%d)" % (ep0.intf_idx)
                    if ep1.intf_idx in devices[ep1.dev_idx].interfaces:
                        raise IOError, "received channel message with invalid second endpoint interface (%d)" % (ep1.intf_idx)

                    if0 = devices[ep0.dev_idx].interfaces[ep0.intf_idx]
                    if1 = devices[ep1.dev_idx].interfaces[ep1.intf_idx]
                    
                    msgs.append(wrapper.LinkMsg.instantiate(legacy.CORE_API_ADD_FLAG,
                                                            ep0.dev_idx,ep0.intf_idx,
                                                            ep1.dev_idx,ep1.intf_idx,
                                                            if1ip4=if0.ip4_addr if if0.HasField("ip4_addr") else None, 
                                                            if2ip4=if1.ip4_addr if if1.HasField("ip4_addr") else None))
                                                       
        # TODO
        # send metadata


        # Finally, set the new experiment ID in the legacy core session as metadata
        # TODO: Append this to the end of metadata above
        msgs.append(wrapper.ConfMsg.instantiate("metadata", 
                                                dataTypes = (coreapi.CONF_DATA_TYPE_STRING,),
                                                dataValues = "experimentId=%s" % (str(message.experimentId))))

        return msgs


    def processApi2Event(self, event, purpose):
        if self.debug:
            self.info('Received event')





