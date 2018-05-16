const Ip4Prefix = '10.0.0.1/24';
const Ip6Prefix = '2001::/64';


class NodeHelper {
    constructor() {
        this.displays = {
            // default router
            0: {
                name: 'node',
                display: 'Default'
            },
            // switch
            4: {
                name: 'switch',
                display: 'Switch'
            },
            // hub
            5: {
                name: 'hub',
                display: 'Hub'
            },
            // wlan
            6: {
                name: 'wlan',
                display: 'WLAN'
            },
            // emane
            10: {
                name: 'emane',
                display: 'EMANE'
            },
            // ptp
            12: {
                name: 'ptp',
                display: 'PTP'
            }
        };

        this.icons = {
            router: 'static/router.svg',
            host: 'static/host.svg',
            PC: 'static/pc.gif',
            mdr: 'static/mdr.svg',
            switch: 'static/lanswitch.svg',
            hub: 'static/hub.svg',
            wlan: 'static/wlan.svg',
            emane: 'static/wlan.svg'
        };

        this.defaultNode = 0;
        this.switchNode = 4;
        this.hubNode = 5;
        this.wlanNode = 6;
        this.emaneNode = 10;
        this.ptpNode = 12;
        this.controlNet = 13;
    }

    isNetworkNode(node) {
        return [
            this.switchNode,
            this.hubNode,
            this.wlanNode,
            this.emaneNode,
            this.ptpNode
        ].includes(node.type);
    }

    isSkipNode(node) {
        return [CoreNodeHelper.ptpNode, CoreNodeHelper.controlNet].includes(node.type);
    }

    getDisplay(nodeType) {
        return this.displays[nodeType];
    }

    getIcon(node) {
        let iconName = this.getDisplay(node.type).name;
        if (node.type === 0) {
            iconName = node.model;
        }
        return this.icons[iconName];
    }
}
const CoreNodeHelper = new NodeHelper();

class CoreNode {
    constructor(id, type, name, x, y) {
        this.id = id;
        this.type = type;
        this.name = name;
        this.model = null;
        this.canvas = null;
        this.icon = null;
        this.opaque = null;
        this.services = [];
        this.x = x;
        this.y = y;
        this.lat = null;
        this.lon = null;
        this.alt = null;
        this.emulation_id = null;
        this.emulation_server = null;
        this.interfaces = {};
        this.emane = null;
    }

    getNetworkNode() {
        const icon = CoreNodeHelper.getIcon(this);

        return {
            id: this.id,
            x: this.x,
            y: this.y,
            label: this.name,
            coreNode: this,
            shape: 'image',
            image: icon
        };
    }

    json() {
        return {
            id: this.id,
            type: this.type,
            name: this.name,
            model: this.model,
            x: this.x,
            y: this.y,
            lat: this.lat,
            lon: this.lon,
            alt: this.alt,
            services: this.services,
            emane: this.emane
        }
    }
}

class CoreLink {
    constructor(nodeOne, nodeTwo, interfaceOne, interfaceTwo) {
        this.nodeOne = nodeOne;
        this.nodeTwo = nodeTwo;
        this.interfaceOne = interfaceOne;
        this.interfaceTwo = interfaceTwo;
        this.bandwidth = null;
        this.delay = null;
        this.loss = null;
        this.duplicate = null;
        this.jitter = null;
    }

    json() {
        return {
            node_one: this.nodeOne,
            node_two: this.nodeTwo,
            interface_one: this.interfaceOne,
            interface_two: this.interfaceTwo,
            options: {
                bandwidth: this.bandwidth,
                delay: this.delay,
                per: this.loss,
                dup: this.duplicate,
                jitter: this.jitter
            }
        }
    }
}

class CoreNetwork {
    constructor(elementId, coreRest) {
        this.coreRest = coreRest;
        this.nodeType = 0;
        this.nodeModel = 'router';
        this.nodeId = 0;
        this.container = document.getElementById(elementId);
        this.nodes = new vis.DataSet();
        this.edges = new vis.DataSet();
        this.links = {};
        this.emaneModels = [];
        this.networkData = {
            nodes: this.nodes,
            edges: this.edges
        };
        this.networkOptions = {
            height: '95%',
            physics: false,
            interaction: {
                selectConnectedEdges: false
            },
            edges: {
                shadow: true,
                width: 3,
                smooth: false,
                color: {
                    color: '#000000'
                }
            },
            nodes: {
                shadow: true
            }
        };
        this.network = new vis.Network(this.container, this.networkData, this.networkOptions);
        this.network.on('doubleClick', this.doubleClick.bind(this));
        this.network.on('dragEnd', this.dragEnd.bind(this));
        this.edges.on('add', this.addEdge.bind(this));
    }

    async initialSession() {
        const session = await this.coreRest.retrieveSession();
        console.log('retrieved session: ', session);
        await this.joinSession(session.id);
        return session;
    }

    async newSession() {
        const session = await this.coreRest.createSession();
        this.coreRest.currentSession = session.id;
        this.reset();
        this.setEmaneModels();
        toastr.success(`Created ${session.id}`, 'Session');
        return session;
    }

    deleteNode(nodeId) {
        // remove node from graph
        this.nodeId = nodeId - 1;
        this.nodes.remove(nodeId);

        // remove node links
        const edges = this.edges.get();
        for (let edge of edges) {
            const link = edge.link;

            if (edge.from === nodeId) {
                this.edges.remove(edge);
                const otherNode = this.getCoreNode(edge.to);
                delete otherNode.interfaces[link.interfaceTwo.id];
                delete this.links[edge.linkId]
            } else if (edge.to === nodeId) {
                this.edges.remove(edge);
                const otherNode = this.getCoreNode(edge.from);
                delete otherNode.interfaces[link.interfaceOne.id];
                delete this.links[edge.linkId]
            }
        }
    }

    getCoreNode(nodeId) {
        return this.nodes.get(nodeId).coreNode;
    }

    async dragEnd(properties) {
        console.log('drag end properties: ', properties);
        if (properties.nodes.length == 1) {
            const nodeId = properties.nodes[0];
            const networkNode = this.nodes.get(nodeId);
            const coreNode = networkNode.coreNode;
            coreNode.x = properties.pointer.canvas.x;
            coreNode.y = properties.pointer.canvas.y;
            if (await this.coreRest.isRunning()) {
                console.log('updated core node location: ', coreNode.x, coreNode.y);
                await this.coreRest.editNode(coreNode);
            }
        }
    }

    reset() {
        this.nodeId = 0;
        this.nodes.clear();
        this.edges.clear();
        this.links = {};
    }

    getCoreNodes() {
        const coreNodes = [];
        for (let node of this.nodes.get()) {
            coreNodes.push(node.coreNode.json());
        }
        return coreNodes;
    }

    addCoreNode(node) {
        const position = node.position;
        const coreNode = new CoreNode(node.id, node.type, node.name, position.x, position.y);
        coreNode.model = node.model;
        coreNode.services = node.services;
        coreNode.emane = node.emane;
        this.nodes.add(coreNode.getNetworkNode());
    }

    nextNodeId() {
        this.nodeId += 1;
        while (true) {
            const node = this.nodes.get(this.nodeId);
            if (node === null) {
                break;
            }
            this.nodeId += 1;
        }
        return this.nodeId;
    }

    async setEmaneModels() {
        const response = await this.coreRest.getEmaneModels();
        console.log('emane models: ', response);
        this.emaneModels = response.models;
    }

    async joinSession(sessionId) {
        this.reset();
        this.coreRest.currentSession = sessionId;
        const session = await this.coreRest.getSession();
        console.log('session info: ', session);
        await this.setEmaneModels();

        const nodes = session.nodes;
        const nodeIds = [0];
        for (let node of nodes) {
            if (CoreNodeHelper.isSkipNode(node)) {
                continue;
            }

            nodeIds.push(node.id);
            this.addCoreNode(node);
        }

        for (let node of nodes) {
            if (!CoreNodeHelper.isNetworkNode(node)) {
                continue;
            }

            const response = await this.coreRest.getLinks(node.id);
            console.log('link response: ', response);
            for (let linkData of response.links) {
                this.createEdgeFromLink(linkData);
            }
        }

        if (nodes.length) {
            this.nodeId = Math.max.apply(Math, nodeIds) || 0;
        } else {
            this.nodeId = 0;
        }

        this.network.fit();

        toastr.success(`Joined ${sessionId}`, 'Session');

        return {
            id: sessionId,
            state: session.state
        };
    }

    createEdgeFromLink(linkData) {
        const fromNode = this.nodes.get(linkData.node1_id).coreNode;
        const toNode = this.nodes.get(linkData.node2_id).coreNode;
        const linkId = `${fromNode.id}-${toNode.id}`;

        let interfaceOne = null;
        if (linkData.interface1_id !== null) {
            interfaceOne = {
                id: linkData.interface1_id,
                ip4: linkData.interface1_ip4,
                ip4mask: linkData.interface1_ip4_mask,
                ip6: linkData.interface1_ip6,
                ip6mask: linkData.interface1_ip6_mask
            };
            fromNode.interfaces[linkData.interface1_id] = interfaceOne;
        }

        let interfaceTwo = null;
        if (linkData.interface2_id !== null) {
            interfaceTwo = {
                id: linkData.interface2_id,
                ip4: linkData.interface2_ip4,
                ip4mask: linkData.interface2_ip4_mask,
                ip6: linkData.interface2_ip6,
                ip6mask: linkData.interface2_ip6_mask
            };
            toNode.interfaces[linkData.interface2_id] = interfaceTwo;
        }

        const link = new CoreLink(fromNode.id, toNode.id, interfaceOne, interfaceTwo);
        link.bandwidth = linkData.bandwidth;
        link.delay = linkData.delay;
        link.duplicate = linkData.dup;
        link.loss = linkData.per;
        link.jitter = linkData.jitter;
        this.links[linkId] = link;

        const edge = {
            recreated: true,
            from: fromNode.id,
            to: toNode.id,
            linkId: linkId,
            link
        };
        this.edges.add(edge);
    }

    async start() {
        const nodes = coreNetwork.getCoreNodes();
        for (let node of nodes) {
            const response = await coreRest.createNode(node);
            console.log('created node: ', response);
        }

        for (let linkId in this.links) {
            const link = this.links[linkId];
            const response = await coreRest.createLink(link.json());
            console.log('created link: ', response);
        }

        return await coreRest.setSessionState(SessionStates.instantiation);
    }

    async doubleClick(properties) {
        const isRunning = await this.coreRest.isRunning();

        // check for terminal interaction
        if (isRunning && properties.nodes.length === 1) {
            const nodeId = properties.nodes[0];
            await this.coreRest.nodeTerminal(nodeId);
            console.log('launched node terminal: ', nodeId);
            return;
        }

        if (isRunning) {
            console.log('node creation disabled, while running');
            return;
        }

        console.log('add node event: ', properties);
        if (properties.nodes.length !== 0) {
            return;
        }

        const {x, y} = properties.pointer.canvas;
        const nodeId = this.nextNodeId();
        const nodeDisplay = CoreNodeHelper.getDisplay(this.nodeType);
        const name = `${nodeDisplay.name}${nodeId}`;
        const coreNode = new CoreNode(nodeId, this.nodeType, name, x, y);
        coreNode.model = this.nodeModel;
        if (coreNode.type === CoreNodeHelper.emaneNode && this.emaneModels.length) {
            coreNode.emane = this.emaneModels[0];
        }
        this.nodes.add(coreNode.getNetworkNode());
        console.log('added node: ', coreNode.getNetworkNode());
    }

    linkAllRouters(nodeId) {
        const toNode = this.getCoreNode(nodeId);
        const routerNodes = this.nodes.get({filter: node => {
            return node.coreNode.model === 'mdr';
        }});
        console.log('router nodes: ', routerNodes);
        for (let fromNode of routerNodes) {
            if (this.edgeExists(fromNode.id, toNode.id)) {
                console.log('ignoring router link that already exists');
                continue;
            }

            const edge = {
                from: fromNode.id,
                to: toNode.id
            };
            this.addEdgeLink(edge, fromNode.coreNode, toNode)
                .catch(err => console.log('add edge link error: ', err));
        }
    }

    edgeExists(fromId, toId) {
        console.log('checking if edge exists: ', fromId, toId);
        console.log('links: ', this.links);
        const idOne = `${fromId}-${toId}`;
        const idTwo = `${toId}-${fromId}`;
        let exists = idOne in this.links;
        exists = exists || idTwo in this.links;
        return exists;
    }

    enableEdgeMode() {
        setTimeout(() => this.network.addEdgeMode(), 250);
    }

    addEdge(_, properties) {
        const edgeId = properties.items[0];
        const edge = this.edges.get(edgeId);

        // ignore edges being recreated
        if (edge.recreated) {
            console.log('ignoring recreated edge');
            return;
        }

        // ignore cycles
        if (edge.from === edge.to) {
            console.log('removing cyclic edge');
            this.edges.remove(edge.id);
            this.enableEdgeMode();
            return;
        }

        // ignore edges that already exist between nodes
        if (this.edgeExists(edge.from, edge.to)) {
            console.log('edge already exists');
            this.enableEdgeMode();
            return false;
        }

        console.log('added edge: ', edgeId, edge);
        const fromNode = this.nodes.get(edge.from).coreNode;
        const toNode = this.nodes.get(edge.to).coreNode;

        this.addEdgeLink(edge, fromNode, toNode)
            .then(function () {
                console.log('create edge link success!');
            })
            .catch(function (err) {
                console.log('create link error: ', err);
            });

        this.enableEdgeMode();
    }

    async addEdgeLink(edge, fromNode, toNode) {
        const linkId = `${fromNode.id}-${toNode.id}`;
        let interfaceOne = null;
        if (fromNode.type === CoreNodeHelper.defaultNode) {
            const fromIps = await this.coreRest.getNodeIps(fromNode.id, Ip4Prefix, Ip6Prefix);
            console.log('from ips: ', fromIps);
            const interfaceOneId = Object.keys(fromNode.interfaces).length;
            interfaceOne = {
                id: interfaceOneId,
                ip4: fromIps.ip4,
                ip4mask: fromIps.ip4mask,
                ip6: fromIps.ip6,
                ip6mask: fromIps.ip6mask
            };
            fromNode.interfaces[interfaceOneId] = interfaceOne;
        }

        let interfaceTwo = null;
        if (toNode.type === CoreNodeHelper.defaultNode) {
            const toIps = await this.coreRest.getNodeIps(toNode.id, Ip4Prefix, Ip6Prefix);
            console.log('to ips: ', toIps);
            const interfaceTwoId = Object.keys(toNode.interfaces).length;
            interfaceTwo = {
                id: interfaceTwoId,
                ip4: toIps.ip4,
                ip4mask: toIps.ip4mask,
                ip6: toIps.ip6,
                ip6mask: toIps.ip6mask
            };
            toNode.interfaces[interfaceTwoId] = interfaceTwo;
        }

        const link = new CoreLink(fromNode.id, toNode.id, interfaceOne, interfaceTwo);
        this.links[linkId] = link;
        edge.linkId = linkId;
        edge.link = link;
        this.edges.update(edge);
    }

    linkMode(enabled) {
        console.log('link mode:', enabled);
        if (enabled) {
            this.network.addEdgeMode();
        } else {
            this.network.disableEditMode();
        }
    }

    setNodeMode(nodeType, model) {
        this.nodeType = nodeType;
        this.nodeModel = model || null;
    }
}
