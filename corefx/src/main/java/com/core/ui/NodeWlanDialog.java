package com.core.ui;

import com.core.Controller;
import com.core.data.CoreNode;
import com.core.rest.WlanConfig;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXTextField;
import javafx.fxml.FXML;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;

public class NodeWlanDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();

    private CoreNode coreNode;

    @FXML
    private JFXTextField rangeTextField;

    @FXML
    private JFXTextField bandwidthTextField;

    @FXML
    private JFXTextField delayTextField;

    @FXML
    private JFXTextField lossTextField;

    @FXML
    private JFXTextField jitterTextField;

    public NodeWlanDialog(Controller controller) {
        super(controller, "/fxml/wlan_dialog.fxml");

        JFXButton saveButton = createButton("Save");
        saveButton.setOnAction(event -> {
            try {
                WlanConfig config = new WlanConfig();
                config.setRange(rangeTextField.getText());
                config.setBandwidth(bandwidthTextField.getText());
                config.setJitter(jitterTextField.getText());
                config.setDelay(delayTextField.getText());
                config.setError(lossTextField.getText());
                getCoreClient().setWlanConfig(coreNode, config);
            } catch (IOException ex) {
                logger.error("error setting wlan config", ex);
                Toast.error("Error setting wlan config");
            }

            close();
        });
        addCancelButton();
    }

    public void showDialog(CoreNode node) {
        coreNode = node;
        setTitle(String.format("%s - WLAN", node.getName()));

        try {
            WlanConfig wlanConfig = getCoreClient().getWlanConfig(coreNode);
            rangeTextField.setText(wlanConfig.getRange());
            bandwidthTextField.setText(wlanConfig.getBandwidth());
            jitterTextField.setText(wlanConfig.getJitter());
            delayTextField.setText(wlanConfig.getDelay());
            lossTextField.setText(wlanConfig.getError());
        } catch (IOException ex) {
            logger.error("error getting wlan config", ex);
            Toast.error("Error getting wlan config");
        }

        show();
    }
}
