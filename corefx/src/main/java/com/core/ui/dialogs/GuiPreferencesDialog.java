package com.core.ui.dialogs;

import com.core.Controller;
import com.core.ui.Toast;
import com.core.utils.ConfigUtils;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXTextField;
import javafx.event.ActionEvent;
import javafx.event.EventHandler;
import javafx.fxml.FXML;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;
import java.util.Properties;

public class GuiPreferencesDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private @FXML JFXTextField xmlFilePathTextField;
    private @FXML JFXTextField shellCommandTextField;
    private @FXML JFXButton saveButton;

    public GuiPreferencesDialog(Controller controller) {
        super(controller, "/fxml/gui_preferences.fxml");
        setTitle("GUI Preferences");
        saveButton = createButton("Save");
        saveButton.setOnAction(onSave);
        addCancelButton();
    }

    private EventHandler<ActionEvent> onSave = event -> {
        Properties properties = getController().getProperties();
        properties.setProperty(ConfigUtils.CORE_XML_PATH, xmlFilePathTextField.getText());
        properties.setProperty(ConfigUtils.SHELL_COMMAND, shellCommandTextField.getText());
        try {
            ConfigUtils.save(properties);
            Toast.success("Updated preferences");
        } catch (IOException ex) {
            Toast.error("Failure to update preferences", ex);
        }
        close();
    };

    public void showDialog() {
        Properties properties = getController().getProperties();
        xmlFilePathTextField.setText(properties.getProperty(ConfigUtils.CORE_XML_PATH));
        shellCommandTextField.setText(properties.getProperty(ConfigUtils.SHELL_COMMAND));
        show();
    }
}
