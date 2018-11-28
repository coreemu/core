package com.core.graph;

import com.core.Controller;
import com.core.data.CoreNode;

class NodeContextMenu extends AbstractNodeContextMenu {
    NodeContextMenu(Controller controller, CoreNode coreNode) {
        super(controller, coreNode);
        setup();
    }

    private void setup() {
        if (controller.getCoreClient().isRunning()) {
            addMenuItem("Manage Services", event -> {
            });
        } else {
            addMenuItem("Services", event -> controller.getNodeServicesDialog().showDialog(coreNode));
            addMenuItem("Delete Node", event -> controller.deleteNode(coreNode));
        }
    }
}
