function createRadio(name, value, label, checked = false) {
    const $formCheck = $('<div>', {class: 'form-check'});
    const $input = $('<input>', {
        class: 'form-check-input',
        type: 'radio',
        name: name,
        checked,
        value
    });
    const $label = $('<label>', {class: 'form-check-label', text: label});
    $formCheck.append([$input, $label]);
    return $formCheck;
}

function createCheckbox(name, value, label, checked = false) {
    const $formCheck = $('<div>', {class: 'form-check col'});
    const $input = $('<input>', {
        class: 'form-check-input',
        type: 'checkbox',
        value,
        name,
        checked
    });
    const $label = $('<label>', {class: 'form-check-label', text: label});
    $formCheck.append([$input, $label]);
    return $formCheck;
}

function createTextbox(name, label, value) {
    const $formGroup = $('<div>', {class: 'form-group'});
    const $label = $('<label>', {text: label});
    const $input = $('<input>', {type: 'text', class: 'form-control', name, value});
    $formGroup.append([$label, $input]);
    return $formGroup;
}

function createTabHeader(id, label, active) {
    let classes = 'nav-link';
    if (active) {
        classes += ' active';
    }
    const $li = $('<li>', {class: 'nav-item'});
    const $a = $('<a>', {class: classes, 'data-toggle': 'tab', href: `#${id}`, role: 'tab', text: label});
    $li.append($a);
    return $li;
}

function createTabPane(id, active) {
    let classes = 'tab-pane fade';
    if (active) {
        classes += ' show active';
    }

    return $('<div>', {class: classes, role: 'tabpanel', id});
}


class ConfigModel {
    constructor(coreRest) {
        this.coreRest = coreRest;
        this.$modal = $('#config-modal');
        this.$title = this.$modal.find('.modal-title');
        this.$tabHeaders = this.$modal.find('.nav-tabs');
        this.$tabContent = this.$modal.find('.tab-content');
        this.$form = this.$modal.find('form');
        this.$saveButton = $('#config-button');
        this.$saveButton.click(this.onClick.bind(this));
        this.$nodeEditModal = $('#nodeedit-modal');
        this.$nodeEditModal.on('click', '#emane-options', this.emaneOptionsClick.bind(this));
        this.$nodeEditModal.on('click', '#emane-model-options', this.emaneModelOptionsClick.bind(this));
    }

    async onClick() {
        const nodeId = this.$nodeEditModal.data('node');
        const configType = this.$modal.data('type');
        console.log('config save clicked: ', nodeId, configType);
        const configs = [];
        for (let input of this.$form.find('input')) {
            const $input = $(input);
            const name = $input.attr('name');
            const dataType = $input.parent().data('type');
            const value = $input.val();
            configs.push({name, value, type: dataType});
        }
        console.log('config data: ', configs);
        await this.coreRest.setConfig({
            name: configType,
            node: nodeId,
            values: configs
        });
        this.$modal.modal('hide');
    }

    showConfig(config) {
        this.$tabHeaders.html('');
        this.$tabContent.html('');
        let initialTab = true;
        for (let group of config.groups) {
            let active = false;
            if (initialTab) {
                initialTab = false;
                active = true;
            }

            console.log('option group: ', group.name);
            const tabId = group.name.toLocaleLowerCase().split(" ").join("-");
            console.log('tab id: ', tabId);
            const $tabHeader = createTabHeader(tabId, group.name, active);
            this.$tabHeaders.append($tabHeader);
            const $tabPane = createTabPane(tabId, active);
            this.$tabContent.append($tabPane);
            for (let option of group.options) {
                const $textbox = createTextbox(option.name, option.label, option.value);
                $textbox.data('type', option.type);
                $tabPane.append($textbox);
            }
        }
        this.$modal.modal('show');
    }

    async emaneOptionsClick(event) {
        this.$nodeEditModal.modal('hide');
        const nodeId = this.$nodeEditModal.data('node');
        const configName = 'emane';
        this.$modal.data('type', configName);
        this.$title.text('EMANE Options');
        const config = await this.coreRest.getConfig({node: nodeId, name: configName});
        console.log('emane options clicked: ', config);
        this.showConfig(config);
        return false;
    }

    async emaneModelOptionsClick(event) {
        this.$nodeEditModal.modal('hide');
        const nodeId = this.$nodeEditModal.data('node');
        const configName = this.$nodeEditModal.find('input[name=emane]:checked').val();
        this.$modal.data('type', configName);
        this.$title.text('EMANE Model Options');
        console.log('emane model clicked: ', configName);
        const config = await this.coreRest.getConfig({node: nodeId, name: configName});
        console.log('emane model options clicked: ', config);
        this.showConfig(config);
        return false;
    }
}


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
                const $checkbox = createCheckbox(service, service, service, checked);
                $row.append([$button, $checkbox]);
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
    constructor(coreRest, coreNetwork, onJoin, deleteCurrent) {
        this.coreRest = coreRest;
        this.coreNetwork = coreNetwork;
        this.onJoin = onJoin;
        this.deleteCurrent = deleteCurrent;
        this.$modal = $('#sessions-modal');
        this.$modal.on('shown.bs.modal', this.onShow.bind(this));
        this.$table = $('#sessions-table');
        this.$table.on('click', 'tbody tr', this.sessionClick.bind(this));
        this.$joinButton = $('#session-join');
        this.$joinButton.click(this.joinClicked.bind(this));
        this.$deleteButton = $('#session-delete');
        this.$deleteButton.click(this.deleteClicked.bind(this));
        this.selectedSession = null;
    }

    async joinClicked() {
        console.log('joining session: ', this.selectedSession);
        if (this.selectedSession === this.coreRest.currentSession) {
            console.log('same session, not changing');
        } else {
            const session = await this.coreNetwork.joinSession(this.selectedSession);
            this.onJoin(session);
        }
        this.$modal.modal('hide');
        return false;
    }

    async deleteClicked(event) {
        console.log('deleting session: ', this.selectedSession);
        await this.coreRest.deleteSession(this.selectedSession);
        if (this.selectedSession === this.coreRest.currentSession) {
            this.deleteCurrent();
        }
        this.$modal.modal('hide');
        return false;
    }

    async sessionClick(event) {
        this.$table.find('tr').removeClass('table-active');
        console.log('event: ', event);
        const $row = $(event.currentTarget);
        $row.addClass('table-active');
        this.selectedSession = $row.data('session');
        this.$joinButton.removeAttr('disabled');
        this.$deleteButton.removeAttr('disabled');
        console.log('selected session: ', this.selectedSession);
    }

    async onShow() {
        console.log('show sessions');
        this.$joinButton.attr('disabled', 'disabled');
        this.$deleteButton.attr('disabled', 'disabled');
        this.$table.find('tbody tr').remove();
        const response = await this.coreRest.getSessions();
        const sessions = response.sessions;
        for (let session of sessions) {
            console.log('show sessions: ', session);
            const $idCell = $('<td>', {text: session.id});
            const $nodeCell = $('<td>', {text: session.nodes});
            const stateName = this.coreRest.getStateName(session.state);
            const $stateCell = $('<td>', {text: stateName});
            const $row = $('<tr>', {class: 'session-join'});
            $row.data('session', session.id);
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
        this.$context = $('#node-context');
        this.$context.click(this.onClick.bind(this));
        this.$linkRfButton = $('#node-linkrf-button');
        this.$deleteButton = $('#node-delete-button');
    }

    async show(nodeId, x, y) {
        const node = this.coreNetwork.getCoreNode(nodeId);
        console.log('context node: ', node);
        if (await this.coreRest.isRunning()) {
            this.$deleteButton.attr('disabled', 'disabled');
        } else {
            this.$deleteButton.removeAttr('disabled');
        }

        console.log('node type: ', node.type);
        if (node.type === CoreNodeHelper.emaneNode || node.type === CoreNodeHelper.wlanNode) {
            this.$linkRfButton.removeClass('d-none');
        } else {
            this.$linkRfButton.addClass('d-none');
        }

        this.$context.data('node', nodeId);
        this.$context.css({
            position: 'absolute',
            left: x,
            top: y
        });
        this.$context.removeClass('d-none');
    }

    hide() {
        this.$context.addClass('d-none');
    }

    async onClick(event) {
        this.$context.addClass('d-none');
        console.log('node context click: ', event);
        const nodeId = this.$context.data('node');
        const $target = $(event.target);
        const option = $target.data('option');
        console.log('node context: ', nodeId, option);
        switch (option) {
            case 'edit':
                await this.nodeEditModal.show(nodeId);
                break;
            case 'services':
                await this.servicesModal.show(nodeId);
                break;
            case 'linkrf':
                console.log('linking all routers');
                this.coreNetwork.linkAllRouters(nodeId);
                break;
            case 'delete':
                this.coreNetwork.deleteNode(nodeId);
                break;
        }

        return false;
    }
}

class NodeEditModal {
    constructor(coreNetwork, coreRest) {
        this.coreNetwork = coreNetwork;
        this.coreRest = coreRest;
        this.$modal = $('#nodeedit-modal');
        this.$form = this.$modal.find('form');
        this.$formCustom = $('#nodeedit-custom');
        this.$editButton = $('#nodeedit-button');
        this.$editButton.click(this.onClick.bind(this));
    }

    addEmaneOptions(node) {
        this.$formCustom.append($('<label>', {class: 'form-label', text: 'EMANE Model'}));
        // add buttons for editing emane and model options
        const $formRow = $('<div>', {class: 'row'});
        const $emaneButton = $('<div>', {class: 'col'}).append(
            $('<a>', {
                    id: 'emane-options',
                    href: '#',
                    class: 'btn btn-primary btn-sm w-100',
                    text: 'EMANE Options'
                }
            ));
        const $modelButton = $('<div>', {class: 'col'}).append(
            $('<a>', {
                    id: 'emane-model-options',
                    href: '#',
                    class: 'btn btn-primary btn-sm w-100',
                    text: 'Model Options'
                }
            ));
        $formRow.append([$emaneButton, $modelButton]);
        this.$formCustom.append($formRow);

        for (let model of this.coreNetwork.emaneModels) {
            const checked = node.emane === model;
            const label = model.split('_')[1];
            const $radio = createRadio('emane', model, label, checked);
            this.$formCustom.append($radio);
        }
    }

    addInterfaceOptions(node) {
        for (let interfaceId in node.interfaces) {
            const nodeInterface = node.interfaces[interfaceId];
            console.log('node interface: ', nodeInterface);
            let $label = $('<label>', {text: `eth${interfaceId}`});
            this.$formCustom.append($label);

            let $inputGroup = $('<div>', {class: 'input-group mb-1'});
            const $ip4Label = $('<div>', {class: 'input-group-prepend'}).append(
                $('<span>', {class: 'input-group-text', text: 'IP4'})
            );
            const $ip4 = $('<input>', {
                class: 'form-control',
                type: 'text',
                name: `interface-${interfaceId}-ip4`,
                value: nodeInterface.ip4
            });
            const $ip4Mask = $('<input>', {
                class: 'form-control',
                type: 'text',
                name: `interface-${interfaceId}-ip4mask`,
                value: nodeInterface.ip4mask
            });
            $inputGroup.append([$ip4Label, $ip4, $ip4Mask]);
            this.$formCustom.append($inputGroup);

            $inputGroup = $('<div>', {class: 'input-group'});
            const $ip6Label = $('<div>', {class: 'input-group-prepend'}).append(
                $('<span>', {class: 'input-group-text', text: 'IP6'})
            );
            const $ip6 = $('<input>', {
                class: 'form-control',
                type: 'text',
                name: `interface-${interfaceId}-ip6`,
                value: nodeInterface.ip6
            });
            const $ip6Mask = $('<input>', {
                class: 'form-control',
                type: 'text',
                name: `interface-${interfaceId}-ip6mask`,
                value: nodeInterface.ip6mask
            });
            $inputGroup.append([$ip6Label, $ip6, $ip6Mask]);
            this.$formCustom.append($inputGroup);
        }
    }

    async show(nodeId) {
        const node = this.coreNetwork.getCoreNode(nodeId);
        this.$modal.data('node', nodeId);
        this.$modal.find('.modal-title').text(`Edit Node: ${node.name}`);
        this.$modal.find('#node-name').val(node.name);

        this.$formCustom.html('');

        // add interface edit
        this.addInterfaceOptions(node);

        // add emane edit
        if (node.type === CoreNodeHelper.emaneNode) {
            this.addEmaneOptions(node);
        }

        this.$modal.modal('show');
    }

    onClick() {
        const $form = this.$modal.find('form');
        const formData = formToJson($form);
        console.log('node edit data: ', formData);
        const nodeId = this.$modal.data('node');
        const node = this.coreNetwork.nodes.get(nodeId);
        if (formData.name) {
            node.label = formData.name;
            node.coreNode.name = formData.name;
            this.coreNetwork.nodes.update(node);
        }

        // deal with interface data
        const interfaceKeys = Object.keys(formData)
            .filter(key => key.startsWith('interface'));
        for (let interfaceKey of interfaceKeys) {
            const value = formData[interfaceKey];
            const interfaceValues = interfaceKey.split('-');
            const interfaceId = interfaceValues[1];
            const field = interfaceValues[2];
            node.coreNode.interfaces[interfaceId][field] = value;
        }

        if (formData.emane !== undefined) {
            node.coreNode.emane = formData.emane;
        }

        this.$modal.modal('hide');
    }
}

class EdgeContext {
    constructor(coreNetwork, edgeEditModal) {
        this.coreNetwork = coreNetwork;
        this.edgeEditModal = edgeEditModal;
        this.$context = $('#edge-context');
        this.$context.click(this.onClick.bind(this));
    }

    show(edgeId, x, y) {
        const edge = this.coreNetwork.edges.get(edgeId);
        console.log('context edge: ', edge);
        this.$context.data('edge', edgeId);
        this.$context.css({
            position: 'absolute',
            left: x,
            top: y
        });
        this.$context.removeClass('d-none');
    }

    hide() {
        this.$context.addClass('d-none');
    }

    onClick(event) {
        this.$context.addClass('d-none');
        console.log('edge context click: ', event);
        const edgeId = this.$context.data('edge');
        const $target = $(event.target);
        const option = $target.data('option');
        console.log('edge context: ', edgeId, option);
        if (option === 'edit') {
            this.edgeEditModal.show(edgeId);
        }
    }
}

class EdgeEditModal {
    constructor(coreNetwork, coreRest) {
        this.coreNetwork = coreNetwork;
        this.coreRest = coreRest;
        this.$modal = $('#linkedit-modal');
        this.$editButton = $('#linkedit-button');
        this.$editButton.click(this.onClick.bind(this));
    }

    show(edgeId) {
        // populate form with current link data
        const edge = this.coreNetwork.edges.get(edgeId);
        const link = edge.link;
        this.$modal.data('link', edgeId);
        this.$modal.find('#link-bandwidth').val(link.bandwidth);
        this.$modal.find('#link-delay').val(link.delay);
        this.$modal.find('#link-per').val(link.loss);
        this.$modal.find('#link-dup').val(link.duplicate);
        this.$modal.find('#link-jitter').val(link.jitter);

        // set modal name and show
        this.$modal.find('.modal-title').text('Edit Edge');
        this.$modal.modal('show');
    }

    async onClick(event) {
        const $form = this.$modal.find('form');
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
        const edgeId = this.$modal.data('link');
        const edge = this.coreNetwork.edges.get(edgeId);
        const link = edge.link;

        link.bandwidth = formData.bandwidth;
        link.delay = formData.delay;
        link.duplicate = formData.duplicate;
        link.loss = formData.loss;
        link.jitter = formData.jitter;

        if (await coreRest.isRunning()) {
            const linkEdit = link.json();
            linkEdit.interface_one = linkEdit.interface_one.id;
            linkEdit.interface_two = linkEdit.interface_two.id;
            await this.coreRest.editLink(linkEdit);
            console.log('link edit success');
        }

        this.$modal.modal('hide');
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
        if (node.model) {
            this.addInfoTable('Model', node.model);
        }
        if (node.emane) {
            this.addInfoTable('EMANE', node.emane);
        }
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
