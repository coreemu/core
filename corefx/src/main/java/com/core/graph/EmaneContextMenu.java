package com.core.graph;

import com.core.Controller;
import com.core.data.CoreNode;

class EmaneContextMenu extends AbstractNodeContextMenu {
    EmaneContextMenu(Controller controller, CoreNode coreNode) {
        super(controller, coreNode);
        setup();
    }

    private void setup() {
        addMenuItem("EMANE Settings",
                event -> controller.getNodeEmaneDialog().showDialog(coreNode));
        if (!controller.getCoreClient().isRunning()) {
            addMenuItem("Mobility",
                    event -> controller.getMobilityDialog().showDialog(coreNode));
            addMenuItem("Link MDRs",
                    event -> controller.getNetworkGraph().linkMdrs(coreNode));
            addMenuItem("Delete Node", event -> controller.deleteNode(coreNode));
        }
    }
}
