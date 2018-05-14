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
