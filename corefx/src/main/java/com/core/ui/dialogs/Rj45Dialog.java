package com.core.ui.dialogs;

import com.core.Controller;
import com.core.data.CoreNode;
import com.core.ui.Toast;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXComboBox;
import javafx.fxml.FXML;
import javafx.stage.Modality;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;
import java.util.List;

public class Rj45Dialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    @FXML private JFXComboBox<String> interfacesComboBox;
    private JFXButton saveButton;

    public Rj45Dialog(Controller controller) {
        super(controller, "/fxml/rj45_dialog.fxml", 600, 150);
        setTitle("Select RJ45 Interface");
        saveButton = createButton("Save");
        addCancelButton();
    }

    public void showDialog(CoreNode node) {
        try {
            List<String> interfaces = getCoreClient().getInterfaces();
            logger.info("local interfaces: {}", interfaces);
            interfacesComboBox.getItems().setAll(interfaces);
            interfacesComboBox.getSelectionModel().selectFirst();
            saveButton.setOnAction(event -> {
                String name = interfacesComboBox.getSelectionModel().getSelectedItem();
                node.setName(name);
                getController().getNetworkGraph().getGraphViewer().repaint();
                close();
            });
            show();
        } catch (IOException ex) {
            Toast.error("Failed to get RJ45 interfaces", ex);
        }
    }
}
