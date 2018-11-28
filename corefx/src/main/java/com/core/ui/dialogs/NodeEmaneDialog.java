package com.core.ui.dialogs;

import com.core.Controller;
import com.core.data.ConfigGroup;
import com.core.data.ConfigOption;
import com.core.data.CoreNode;
import com.core.ui.Toast;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXComboBox;
import javafx.event.ActionEvent;
import javafx.fxml.FXML;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;
import java.util.List;

public class NodeEmaneDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private CoreNode coreNode;
    @FXML private JFXComboBox<String> modelCombo;
    @FXML private JFXButton modelButton;
    @FXML private JFXButton emaneButton;

    public NodeEmaneDialog(Controller controller) {
        super(controller, "/fxml/node_emane_dialog.fxml");

        JFXButton saveButton = createButton("Save");
        saveButton.setOnAction(event -> {
            String model = modelCombo.getSelectionModel().getSelectedItem();
            coreNode.setEmane(model);
            close();
        });
        addCancelButton();

        emaneButton.setOnAction(this::emaneButtonHandler);
        modelButton.setOnAction(this::emaneModelButtonHandler);
    }

    public void setModels(List<String> models) {
        models.sort(String::compareTo);
        modelCombo.getItems().setAll(models);
        modelCombo.getSelectionModel().selectFirst();
    }

    public List<String> getModels() {
        return modelCombo.getItems();
    }

    private void emaneButtonHandler(ActionEvent event) {
        try {
            List<ConfigGroup> configGroups = getCoreClient().getEmaneConfig(coreNode);
            logger.debug("emane model config: {}", configGroups);
            String title = String.format("%s EMANE Config", coreNode.getName());
            getController().getConfigDialog().showDialog(title, configGroups, () -> {
                List<ConfigOption> options = getController().getConfigDialog().getOptions();
                try {
                    getCoreClient().setEmaneConfig(coreNode, options);
                } catch (IOException ex) {
                    logger.error("set emane config error", ex);
                }
            });
        } catch (IOException ex) {
            Toast.error("error getting emane model config", ex);
        }
    }

    private void emaneModelButtonHandler(ActionEvent event) {
        String model = modelCombo.getSelectionModel().getSelectedItem();
        displayEmaneModelConfig(coreNode.getId(), model);
    }

    public void displayEmaneModelConfig(Integer id, String model) {
        try {
            List<ConfigGroup> configGroups = getCoreClient().getEmaneModelConfig(id, model);
            logger.debug("emane model config: {}", configGroups);
            String title = String.format("EMANE(%s) %s Config", id, model);
            getController().getConfigDialog().showDialog(title, configGroups, () -> {
                List<ConfigOption> options = getController().getConfigDialog().getOptions();
                try {
                    getCoreClient().setEmaneModelConfig(id, model, options);
                } catch (IOException ex) {
                    Toast.error("set emane model config error", ex);
                }
            });
        } catch (IOException ex) {
            Toast.error("error getting emane model config", ex);
        }
    }

    public void showDialog(CoreNode node) {
        coreNode = node;
        setTitle(String.format("%s - EMANE", node.getName()));
        show();
    }
}
