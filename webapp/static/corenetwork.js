const NodeTypes = {
    // default router
    0: {
        name: 'node'
    },
    // switch
    4: {
        name: 'switch'
    },
    // hub
    5: {
        name: 'hub'
    },
    // wlan
    6: {
        name: 'wlan'
    }
};

class CoreNode {
    constructor(id, name, x, y) {
        this.id = id;
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
    }

    getNetworkNode() {
        return {
            id: this.id,
            x: this.x,
            y: this.y,
            label: this.name,
            node: this
            //color: '#FFF',
            //shape: 'image',
            //shapeProperties: {
            //    useBorderWithImage: true
            //},
            //image: nodeMode.image,
            //type: nodeMode.nodeType
        };
    }
}

class CoreNetwork {
    constructor(elementId) {
        this.nodeType = NodeTypes['0'];
        this.nodeModel = null;
        this.nodeId = 0;
        this.container = document.getElementById(elementId);
        this.nodes = new vis.DataSet();
        this.edges = new vis.DataSet();
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
        this.network.on('doubleClick', this.addNode.bind(this));
        this.edges.on('add', this.addEdge.bind(this));
    }

    nextNodeId() {
        this.nodeId += 1;
        return this.nodeId;
    }

    addNode(properties) {
        console.log('add node event: ', properties);
        if (properties.nodes.length === 0) {
            const {x, y} = properties.pointer.canvas;
            const nodeId = this.nextNodeId();
            const name = `${this.nodeType.name}${nodeId}`;
            const coreNode = new CoreNode(nodeId, name, x, y);
            coreNode.model = this.nodeModel;
            this.nodes.add(coreNode.getNetworkNode());
            console.log('added node: ', coreNode.getNetworkNode());
        }
    }

    addEdge(_, properties) {
        const edgeId = properties.items[0];
        const edge = this.edges.get(edgeId);
        console.log('added edge: ', edgeId, edge);
        if (edge.from === edge.to) {
            console.log('removing cyclic edge');
            this.edges.remove(edge.id);
        }

        // keep edge mode enabled
        setTimeout(() => this.network.addEdgeMode(), 250);
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
        this.nodeType = NodeTypes[nodeType];
        this.nodeModel = model || null;
    }
}
