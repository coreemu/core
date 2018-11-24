package com.core.graph;

import com.core.Controller;
import com.core.data.CoreLink;

class LinkContextMenu extends GraphContextMenu {
    final CoreLink coreLink;

    LinkContextMenu(Controller controller, CoreLink coreLink) {
        super(controller);
        this.coreLink = coreLink;
        setup();
    }

    private void setup() {
        if (!controller.getCoreClient().isRunning()) {
            addMenuItem("Delete Link",
                    event -> controller.getNetworkGraph().removeLink(coreLink));
        }
    }
}
