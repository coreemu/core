package com.core.ui.dialogs;

import com.core.Controller;
import com.core.data.WlanConfig;
import com.core.data.CoreNode;
import com.core.ui.Toast;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXTextField;
import javafx.fxml.FXML;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;

public class NodeWlanDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private final JFXButton saveButton;
    private CoreNode coreNode;
    @FXML private JFXTextField rangeTextField;
    @FXML private JFXTextField bandwidthTextField;
    @FXML private JFXTextField delayTextField;
    @FXML private JFXTextField lossTextField;
    @FXML private JFXTextField jitterTextField;

    public NodeWlanDialog(Controller controller) {
        super(controller, "/fxml/wlan_dialog.fxml");

        saveButton = createButton("Save");
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

    private void setDisabled(boolean isDisabled) {
        rangeTextField.setDisable(isDisabled);
        bandwidthTextField.setDisable(isDisabled);
        jitterTextField.setDisable(isDisabled);
        delayTextField.setDisable(isDisabled);
        lossTextField.setDisable(isDisabled);
        saveButton.setDisable(isDisabled);
    }

    public void showDialog(CoreNode node) {
        coreNode = node;
        setTitle(String.format("%s - WLAN", node.getName()));
        setDisabled(getCoreClient().isRunning());

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
