package com.core.ui;

import com.core.Controller;
import com.core.client.ICoreClient;
import com.core.data.CoreInterface;
import com.core.data.CoreLink;
import com.core.data.CoreLinkOptions;
import com.core.data.CoreNode;
import com.core.graph.NetworkGraph;
import com.jfoenix.controls.JFXTextField;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;

public class LinkDetails extends DetailsPanel {
    private static final Logger logger = LogManager.getLogger();

    public LinkDetails(Controller controller) {
        super(controller);
    }

    public void setLink(CoreLink link) {
        NetworkGraph graph = controller.getNetworkGraph();
        ICoreClient coreClient = controller.getCoreClient();
        clear();

        setTitle("Link Details");
        addSeparator();

        CoreNode nodeOne = graph.getVertex(link.getNodeOne());
        CoreInterface interfaceOne = link.getInterfaceOne();
        addLabel(nodeOne.getName());
        if (interfaceOne != null) {
            addInterface(interfaceOne);
        }

        CoreNode nodeTwo = graph.getVertex(link.getNodeTwo());
        CoreInterface interfaceTwo = link.getInterfaceTwo();
        addLabel(nodeTwo.getName());
        if (interfaceTwo != null) {
            addInterface(interfaceTwo);
        }

        addLabel("Properties");
        JFXTextField bandwidthField = addIntegerRow("Bandwidth (bps)", link.getOptions().getBandwidth());
        JFXTextField delayField = addIntegerRow("Delay (us)", link.getOptions().getDelay());
        JFXTextField jitterField = addIntegerRow("Jitter (us)", link.getOptions().getJitter());
        JFXTextField lossField = addDoubleRow("Loss (%)", link.getOptions().getPer());
        JFXTextField dupsField = addIntegerRow("Duplicate (%)", link.getOptions().getDup());
        addButton("Update", event -> {
            CoreLinkOptions options = link.getOptions();
            options.setBandwidth(getInteger(bandwidthField));
            options.setDelay(getInteger(delayField));
            options.setJitter(getInteger(jitterField));
            options.setPer(getDouble(lossField));
            options.setDup(getInteger(dupsField));

            if (coreClient.isRunning()) {
                try {
                    coreClient.editLink(link);
                    Toast.info("Link updated!");
                } catch (IOException ex) {
                    Toast.error("Failure to update link", ex);
                }
            }
        });
    }
}
