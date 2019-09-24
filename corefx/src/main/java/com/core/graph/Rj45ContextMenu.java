package com.core.graph;

import com.core.Controller;
import com.core.data.CoreNode;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

class Rj45ContextMenu extends AbstractNodeContextMenu {
    private static final Logger logger = LogManager.getLogger();

    Rj45ContextMenu(Controller controller, CoreNode coreNode) {
        super(controller, coreNode);
        setup();
    }

    private void setup() {
        if (!controller.getCoreClient().isRunning()) {
            addMenuItem("Delete Node", event -> controller.deleteNode(coreNode));
        }
    }
}
