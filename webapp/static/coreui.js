class ServiceModal {
    constructor(coreRest) {
        this.coreRest = coreRest;
        this.$modal = $('#service-modal');
        this.$title = this.$modal.find('.modal-title');
        this.$saveButton = $('#service-button');
        this.$saveButton.click(this.onClick.bind(this));
    }

    async show(service) {
        this.$title.text(`Edit ${service}`);
        this.$modal.modal('show');
    }

    async onClick() {

    }
}

class ServicesModal {
    constructor(coreRest, coreNetwork, serviceModal) {
        this.coreRest = coreRest;
        this.coreNetwork = coreNetwork;
        this.serviceModal = serviceModal;
        this.$modal = $('#services-modal');
        this.$modal.on('click', '.service-button', this.editService.bind(this));
        this.$form = this.$modal.find('form');
        this.$serviceGroup = $('#service-group');
        this.$serviceGroup.on('change', this.groupChange.bind(this));
        this.$servicesList = $('#services-list');
        this.$saveButton = $('#services-button');
        this.$saveButton.click(this.saveClicked.bind(this));
        this.defaultServices = {
            mdr: new Set(["zebra", "OSPFv3MDR", "IPForward"]),
            PC: new Set(["DefaultRoute"]),
            prouter: new Set(["zebra", "OSPFv2", "OSPFv3", "IPForward"]),
            router: new Set(["zebra", "OSPFv2", "OSPFv3", "IPForward"]),
            host: new Set(["DefaultRoute", "SSH"])
        };
        this.node = null;
        this.nodeDefaults = null;
        this.serviceGroups = null;
        this.serviceOptions = new Map();
        this.$currentGroup = null;
    }

    editService(event) {
        //event.preventDefault();
        const $target = $(event.target);
        const service = $target.parent().parent().find('label').text();
        console.log('edit service: ', service);
        this.$modal.modal('hide');
        this.serviceModal.show(service);
        return false;
    }

    async show(nodeId) {
        // get node and set default services for node type
        this.node = this.coreNetwork.getCoreNode(nodeId);
        if (this.node.services.length) {
            this.nodeDefaults = new Set(this.node.services);
        } else {
            this.nodeDefaults = this.defaultServices[this.node.model] || new Set();
        }

        // retrieve service groups
        this.serviceGroups = await coreRest.getServices(nodeId);

        // clear data
        this.$serviceGroup.html('');
        this.$servicesList.html('');
        this.serviceOptions.clear();

        // set title
        this.$modal.find('.modal-title').text(`Services: ${this.node.name}`);

        // generate service form options
        for (let group in this.serviceGroups) {
            const $option = $('<option>', {value: group, text: group});
            this.$serviceGroup.append($option);

            const services = this.serviceGroups[group];
            console.log('services: ', services);
            const $formGroup = $('<div>', {class: 'form-group d-none'});
            this.serviceOptions.set(group, $formGroup);
            this.$servicesList.append($formGroup);
            for (let service of services) {
                const checked = this.nodeDefaults.has(service);
                const $row = $('<div>', {class: 'row mb-1'});
                const $button = $('<div>', {class: 'col-1'})
                    .append($('<a>', {text: 'Edit', href: '#', class: 'btn btn-primary btn-sm service-button'}));
                const $formCheck = $('<div>', {class: 'form-check col'});
                const $input = $('<input>', {
                    class: 'form-check-input',
                    type: 'checkbox',
                    value: service,
                    name: service,
                    checked
                });
                const $label = $('<label>', {class: 'form-check-label', text: service});
                $formCheck.append([$input, $label]);
                $row.append([$button, $formCheck]);
                $formGroup.append($row);
            }
        }

        this.$serviceGroup.change();
        this.$modal.modal('show');
    }

    groupChange(event) {
        const group = $(event.target).val();
        if (this.$currentGroup) {
            this.$currentGroup.addClass('d-none');
        }
        this.$currentGroup = this.serviceOptions.get(group);
        this.$currentGroup.removeClass('d-none');
    }

    saveClicked() {
        let services = this.$form.serializeArray();
        services = services.map(x => x.value);
        console.log('services save clicked: ', services);
        this.node.services = services;
        this.$modal.modal('hide');
    }
}

class SessionsModal {
    constructor(coreRest, coreNetwork, onJoin) {
        this.coreRest = coreRest;
        this.coreNetwork = coreNetwork;
        this.onJoin = onJoin;
        this.$modal = $('#sessions-modal');
        this.$modal.on('shown.bs.modal', this.onShow.bind(this));
        this.$table = $('#sessions-table');
        this.$table.on('click', 'td', this.onClick.bind(this));
    }

    async onClick(event) {
        const sessionId = $(event.target).parent('tr').data('session');
        console.log('clicked session to join: ', sessionId);
        if (sessionId === this.coreRest.currentSession) {
            console.log('same session, not changing');
        } else {
            const session = await this.coreNetwork.joinSession(sessionId);
            this.onJoin(session);
            this.$modal.modal('hide');
        }
    }

    async onShow() {
        console.log('show sessions');
        this.$table.find('tbody tr').remove();
        const response = await this.coreRest.getSessions();
        const sessions = response.sessions;
        for (let session of sessions) {
            console.log('show sessions: ', session);
            const $idCell = $('<td>', {text: session.id});
            const $nodeCell = $('<td>', {text: session.nodes});
            const stateName = this.coreRest.getStateName(session.state);
            const $stateCell = $('<td>', {text: stateName});
            const $row = $('<tr>', {class: 'session-join', 'data-session': session.id});
            $row.append([$idCell, $nodeCell, $stateCell]);
            this.$table.find('tbody').append($row);
        }
    }
}

class NodeContext {
    constructor(coreNetwork, coreRest, nodeEditModal, servicesModal) {
        this.coreNetwork = coreNetwork;
        this.coreRest = coreRest;
        this.nodeEditModal = nodeEditModal;
        this.servicesModal = servicesModal;
        this.$nodeContext = $('#node-context');
        this.$linkRfButton = $('#node-linkrf-button');
        this.$deleteButton = $('#node-delete-button');
        this.onClick();
    }

    show(nodeId, x, y) {
        const node = this.coreNetwork.getCoreNode(nodeId);
        console.log('context node: ', node);
        this.coreRest.isRunning()
            .then(isRunning => {
                if (isRunning) {
                    this.$deleteButton.attr('disabled', 'disabled');
                } else {
                    this.$deleteButton.removeAttr('disabled');
                }

                console.log('node type: ', node.type);
                if (node.type === CoreNodeHelper.wlanNode) {
                    this.$linkRfButton.removeClass('d-none');
                } else {
                    this.$linkRfButton.addClass('d-none');
                }

                this.$nodeContext.data('node', nodeId);
                this.$nodeContext.css({
                    position: 'absolute',
                    left: x,
                    top: y
                });
                this.$nodeContext.removeClass('d-none');
            })
            .catch(function (err) {
                console.log('error checking is session is running: ', err);
            });
    }

    hide() {
        this.$nodeContext.addClass('d-none');
    }

    onClick() {
        const self = this;
        this.$nodeContext.click(function (event) {
            self.$nodeContext.addClass('d-none');
            console.log('node context click: ', event);
            const nodeId = self.$nodeContext.data('node');
            const $target = $(event.target);
            const option = $target.data('option');
            console.log('node context: ', nodeId, option);
            switch (option) {
                case 'edit':
                    self.nodeEditModal.show(nodeId);
                    break;
                case 'services':
                    self.servicesModal.show(nodeId)
                        .catch(function (err) {
                            console.log('error showing services modal: ', err);
                        });
                    break;
                case 'linkrf':
                    console.log('linking all routers');
                    self.coreNetwork.linkAllRouters(nodeId);
                    break;
                case 'delete':
                    self.coreNetwork.deleteNode(nodeId);
                    break;
            }
        });
    }
}

class NodeEditModal {
    constructor(coreNetwork) {
        this.coreNetwork = coreNetwork;
        this.$nodeEditModal = $('#nodeedit-modal');
        this.$nodeEditButton = $('#nodeedit-button');
        this.onClick();
    }

    show(nodeId) {
        const node = this.coreNetwork.getCoreNode(nodeId);
        this.$nodeEditModal.data('node', nodeId);
        this.$nodeEditModal.find('.modal-title').text(`Edit Node: ${node.name}`);
        this.$nodeEditModal.find('#node-name').val(node.name);
        this.$nodeEditModal.modal('show');
    }

    onClick() {
        const self = this;
        this.$nodeEditButton.click(function () {
            const $form = self.$nodeEditModal.find('form');
            const formData = formToJson($form);
            console.log('node edit data: ', formData);
            const nodeId = self.$nodeEditModal.data('node');
            const node = self.coreNetwork.nodes.get(nodeId);
            if (formData.name) {
                node.label = formData.name;
                node.coreNode.name = formData.name;
                self.coreNetwork.nodes.update(node);
            }
            self.$nodeEditModal.modal('hide');
        });
    }
}

class EdgeContext {
    constructor(coreNetwork, edgeEditModal) {
        this.coreNetwork = coreNetwork;
        this.edgeEditModal = edgeEditModal;
        this.$edgeContext = $('#edge-context');
        this.onClick();
    }

    show(edgeId, x, y) {
        const edge = this.coreNetwork.edges.get(edgeId);
        console.log('context edge: ', edge);
        this.$edgeContext.data('edge', edgeId);
        this.$edgeContext.css({
            position: 'absolute',
            left: x,
            top: y
        });
        this.$edgeContext.removeClass('d-none');
    }

    hide() {
        this.$edgeContext.addClass('d-none');
    }

    onClick() {
        const self = this;
        this.$edgeContext.click(function (event) {
            self.$edgeContext.addClass('d-none');
            console.log('edge context click: ', event);
            const edgeId = self.$edgeContext.data('edge');
            const $target = $(event.target);
            const option = $target.data('option');
            console.log('edge context: ', edgeId, option);
            if (option === 'edit') {
                self.edgeEditModal.show(edgeId);
            }
        });
    }
}

class EdgeEditModal {
    constructor(coreNetwork, coreRest) {
        this.coreNetwork = coreNetwork;
        this.coreRest = coreRest;
        this.$linkEditButton = $('#linkedit-button');
        this.$linkEditModal = $('#linkedit-modal');
        this.onClick();
    }

    show(edgeId) {
        // populate form with current link data
        const edge = this.coreNetwork.edges.get(edgeId);
        const link = edge.link;
        this.$linkEditModal.data('link', edgeId);
        this.$linkEditModal.find('#link-bandwidth').val(link.bandwidth);
        this.$linkEditModal.find('#link-delay').val(link.delay);
        this.$linkEditModal.find('#link-per').val(link.loss);
        this.$linkEditModal.find('#link-dup').val(link.duplicate);
        this.$linkEditModal.find('#link-jitter').val(link.jitter);

        // set modal name and show
        this.$linkEditModal.find('.modal-title').text('Edit Edge');
        this.$linkEditModal.modal('show');
    }

    onClick() {
        const self = this;
        this.$linkEditButton.click(function () {
            const $form = self.$linkEditModal.find('form');
            const formData = {};
            $form.serializeArray().map(function (x) {
                let value = x.value;
                if (value === '') {
                    value = null;
                } else if (!isNaN(value)) {
                    value = parseInt(value);
                }
                formData[x.name] = value;
            });
            console.log('link edit data: ', formData);
            const edgeId = self.$linkEditModal.data('link');
            const edge = self.coreNetwork.edges.get(edgeId);
            const link = edge.link;

            link.bandwidth = formData.bandwidth;
            link.delay = formData.delay;
            link.duplicate = formData.duplicate;
            link.loss = formData.loss;
            link.jitter = formData.jitter;

            coreRest.isRunning()
                .then(function (isRunning) {
                    if (isRunning) {
                        const linkEdit = link.json();
                        linkEdit.interface_one = linkEdit.interface_one.id;
                        linkEdit.interface_two = linkEdit.interface_two.id;
                        return self.coreRest.editLink(linkEdit);
                    }
                })
                .then(function (response) {
                    console.log('link edit success');
                })
                .catch(function (err) {
                    console.log('error editing link: ', err);
                });

            self.$linkEditModal.modal('hide');
        });
    }
}

class InfoPanel {
    constructor(coreNetwork) {
        this.coreNetwork = coreNetwork;
        this.$infoCard = $('#info-card');
        this.$infoCardTable = $('#info-card-table');
        this.$infoCardHeader = $('#info-card-header');
        this.coreNetwork.nodes.on('remove', this.onNodeDelete.bind(this));
        this.coreNetwork.edges.on('remove', this.onEdgeDelete.bind(this));
    }

    onNodeDelete(_, properties) {
        if (properties.items.length !== 1) {
            return;
        }

        const nodeId = properties.items[0];
        if (nodeId === this.$infoCard.data('node')) {
            this.hide();
        }
    }

    onEdgeDelete(_, properties) {
        if (properties.items.length !== 1) {
            return;
        }

        const edgeId = properties.items[0];
        if (edgeId === this.$infoCard.data('edge')) {
            this.hide();
        }
    }

    addInfoTable(name, value) {
        const $nameCell = $('<td>', {text: name});
        const $valueCell = $('<td>', {text: value});
        const $row = $('<tr>').append([$nameCell, $valueCell]);
        this.$infoCardTable.find('tbody').append($row);
    }

    show() {
        this.$infoCard.removeClass('visible invisible');
        this.$infoCard.addClass('visible');
    }

    hide() {
        this.$infoCard.removeClass('visible invisible');
        this.$infoCard.addClass('invisible');
    }

    addInterfaceInfo(nodeInterface) {
        this.addInfoTable('Interface', `eth${nodeInterface.id}`);
        if (nodeInterface.ip4) {
            this.addInfoTable('IP4', `${nodeInterface.ip4}/${nodeInterface.ip4mask}`);
        }
        if (nodeInterface.ip6) {
            this.addInfoTable('IP6', `${nodeInterface.ip6}/${nodeInterface.ip6mask}`);
        }
    }

    showNode(nodeId) {
        const node = coreNetwork.getCoreNode(nodeId);
        this.$infoCard.data('node', nodeId);
        this.$infoCardHeader.text(node.name);
        this.$infoCardTable.find('tbody tr').remove();
        this.addInfoTable('Model', node.model);
        this.addInfoTable('X', node.x);
        this.addInfoTable('Y', node.y);
        for (let interfaceId in node.interfaces) {
            const nodeInterface = node.interfaces[interfaceId];
            console.log('node interface: ', nodeInterface);
            this.addInterfaceInfo(nodeInterface);
        }
        this.show();
    }

    showEdge(edgeId) {
        const edge = coreNetwork.edges.get(edgeId);
        const link = edge.link;
        const nodeOne = coreNetwork.getCoreNode(link.nodeOne);
        const nodeTwo = coreNetwork.getCoreNode(link.nodeTwo);
        console.log('clicked edge: ', link);
        this.$infoCard.data('edge', edgeId);
        this.$infoCard.addClass('visible');
        this.$infoCardHeader.text('Edge');
        this.$infoCardTable.find('tbody tr').remove();
        const interfaceOne = link.interfaceOne;
        if (interfaceOne) {
            this.addInfoTable(nodeOne.name, null);
            this.addInterfaceInfo(interfaceOne);
        }
        const interfaceTwo = link.interfaceTwo;
        if (interfaceTwo) {
            this.addInfoTable(nodeTwo.name, null);
            this.addInterfaceInfo(interfaceTwo);
        }
        this.addInfoTable('Bandwidth', edge.link.bandwidth);
        this.addInfoTable('Delay', edge.link.delay);
        this.addInfoTable('Duplicate', edge.link.duplicate);
        this.addInfoTable('Loss', edge.link.loss);
        this.addInfoTable('Jitter', edge.link.jitter);
        this.show();
    }
}
