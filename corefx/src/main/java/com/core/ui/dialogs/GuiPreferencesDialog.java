package com.core.ui.dialogs;

import com.core.Controller;
import com.core.ui.Toast;
import com.core.utils.ConfigUtils;
import com.core.utils.Configuration;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXColorPicker;
import com.jfoenix.controls.JFXTextField;
import javafx.event.ActionEvent;
import javafx.event.EventHandler;
import javafx.fxml.FXML;
import javafx.scene.paint.Color;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;

public class GuiPreferencesDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    @FXML private JFXTextField xmlFilePathTextField;
    @FXML private JFXTextField mobilityFilePathTextField;
    @FXML private JFXTextField shellCommandTextField;
    @FXML private JFXTextField iconPathTextField;
    @FXML private JFXColorPicker nodeLabelColorPicker;
    @FXML private JFXColorPicker nodeLabelBackgroundColorPicker;
    @FXML private JFXButton saveButton;

    public GuiPreferencesDialog(Controller controller) {
        super(controller, "/fxml/gui_preferences.fxml");
        setTitle("GUI Preferences");
        saveButton = createButton("Save");
        saveButton.setOnAction(onSave);
        addCancelButton();
    }

    private EventHandler<ActionEvent> onSave = event -> {
        Configuration configuration = getController().getConfiguration();
        configuration.setXmlPath(xmlFilePathTextField.getText());
        configuration.setMobilityPath(mobilityFilePathTextField.getText());
        configuration.setShellCommand(shellCommandTextField.getText());
        configuration.setIconPath(iconPathTextField.getText());
        configuration.setNodeLabelColor(nodeLabelColorPicker.getValue().toString());
        configuration.setNodeLabelBackgroundColor(nodeLabelBackgroundColorPicker.getValue().toString());
        getController().getNetworkGraph().updatePreferences(configuration);
        try {
            ConfigUtils.save(configuration);
            Toast.success("Updated preferences");
        } catch (IOException ex) {
            Toast.error("Failure to update preferences", ex);
        }
        close();
    };

    public void showDialog() {
        Configuration configuration = getController().getConfiguration();
        xmlFilePathTextField.setText(configuration.getXmlPath());
        mobilityFilePathTextField.setText(configuration.getMobilityPath());
        shellCommandTextField.setText(configuration.getShellCommand());
        iconPathTextField.setText(configuration.getIconPath());
        nodeLabelColorPicker.setValue(Color.web(configuration.getNodeLabelColor()));
        nodeLabelBackgroundColorPicker.setValue(Color.web(configuration.getNodeLabelBackgroundColor()));
        show();
    }
}
