class ServicesModal {
    constructor(coreRest, coreNetwork) {
        this.coreRest = coreRest;
        this.coreNetwork = coreNetwork;
        this.$servicesModal = $('#services-modal');
        this.$servicesForm = this.$servicesModal.find('form');
        this.$serviceGroup = $('#service-group');
        this.$servicesList = $('#services-list');
        this.$servicesButton = $('#services-button');
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
        this.groupChange();
        this.saveClicked();
    }

    async show(nodeId) {
        this.node = this.coreNetwork.getCoreNode(nodeId);
        if (this.node.services.length) {
            this.nodeDefaults = new Set(this.node.services);
        } else {
            this.nodeDefaults = this.defaultServices[this.node.model] || new Set();
        }
        this.serviceGroups = await coreRest.getServices(nodeId);

        // clear data
        this.$serviceGroup.html('');
        this.$servicesList.html('');
        this.serviceOptions.clear();

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
                const $formCheck = $('<div>', {class: 'form-check'});
                const $input = $('<input>', {
                    class: 'form-check-input',
                    type: 'checkbox',
                    value: service,
                    name: service,
                    checked
                });
                const $label = $('<label>', {class: 'form-check-label', text: service});
                $formCheck.append($input);
                $formCheck.append($label);
                $formGroup.append($formCheck);
            }
        }

        this.$serviceGroup.change();
        this.$servicesModal.modal('show');
    }

    groupChange() {
        const self = this;
        this.$serviceGroup.on('change', function () {
            const group = $(this).val();
            if (self.$currentGroup) {
                self.$currentGroup.addClass('d-none');
            }
            self.$currentGroup = self.serviceOptions.get(group);
            self.$currentGroup.removeClass('d-none');
        });
    }

    saveClicked() {
        const self = this;
        this.$servicesButton.click(function () {
            let services = self.$servicesForm.serializeArray();
            services = services.map(x => x.value);
            console.log('services save clicked: ', services);
            self.node.services = services;
            self.$servicesModal.modal('hide');
        });
    }
}

class SessionsModal {
    constructor(coreRest, coreNetwork, onJoin) {
        this.coreRest = coreRest;
        this.coreNetwork = coreNetwork;
        this.onJoin = onJoin;
        this.$sessionsModal = $('#sessions-modal');
        this.$sessionsTable = $('#sessions-table');
        this.onShow();
        this.onClick();
    }

    onClick() {
        const self = this;
        this.$sessionsTable.on('click', 'td', function (event) {
            const sessionId = $(this).parent('tr').data('session');
            console.log('clicked session to join: ', sessionId);
            if (sessionId === self.coreRest.currentSession) {
                console.log('same session, not changing');
            } else {
                self.coreNetwork.joinSession(sessionId)
                    .then(function (session) {
                        self.onJoin(session);
                        self.$sessionsModal.modal('hide');
                    })
                    .catch(function (err) {
                        console.log('join session error: ', err);
                    });
            }
        });
    }

    onShow() {
        const self = this;
        this.$sessionsModal.on('shown.bs.modal', function () {
            console.log('show sessions');
            self.$sessionsTable.find('tbody tr').remove();
            self.coreRest.getSessions()
                .then(function (response) {
                    const sessions = response.sessions;
                    for (let session of sessions) {
                        console.log('show sessions: ', session);
                        const $idCell = $('<td>', {text: session.id});
                        const $nodeCell = $('<td>', {text: session.nodes});
                        const stateName = self.coreRest.getStateName(session.state);
                        const $stateCell = $('<td>', {text: stateName});
                        const $row = $('<tr>', {class: 'session-join', 'data-session': session.id});
                        $row.append([$idCell, $nodeCell, $stateCell]);
                        self.$sessionsTable.find('tbody').append($row);
                    }
                })
                .catch(function (err) {
                    console.log('error getting sessions: ', err);
                });
        });
    }
}

class NodeContext {
    constructor(coreNetwork, nodeEditModal, servicesModal) {
        this.coreNetwork = coreNetwork;
        this.nodeEditModal = nodeEditModal;
        this.servicesModal = servicesModal;
        this.$nodeContext = $('#node-context');
        this.onClick();
    }

    show(nodeId, x, y) {
        const node = this.coreNetwork.nodes.get(nodeId);
        console.log('context node: ', node);
        this.$nodeContext.data('node', nodeId);
        this.$nodeContext.css({
            position: 'absolute',
            left: x,
            top: y
        });
        this.$nodeContext.removeClass('d-none');
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
            if (option === 'edit') {
                self.nodeEditModal.show(nodeId);
            } else if (option === 'services') {
                self.servicesModal.show(nodeId)
                    .catch(function (err) {
                        console.log('error showing services modal: ', err);
                    });
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
        this.$infoCard.addClass('visible');
        this.$infoCardHeader.text('Edge');
        this.$infoCardTable.find('tbody tr').remove();
        this.addInfoTable(nodeOne.name, null);
        const interfaceOne = link.interfaceOne;
        if (interfaceOne) {
            this.addInterfaceInfo(interfaceOne);
        }
        this.addInfoTable(nodeTwo.name, null);
        const interfaceTwo = link.interfaceTwo;
        if (interfaceTwo) {
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
