package com.core.ui;

import com.core.Controller;
import com.core.data.Hook;
import com.core.data.SessionState;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXComboBox;
import com.jfoenix.controls.JFXTextArea;
import com.jfoenix.controls.JFXTextField;
import javafx.fxml.FXML;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.Arrays;
import java.util.stream.Collectors;

public class HookDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private static final String DEFAULT_DATA = "#!/bin/sh\n" +
            "# session hook script; write commands here to execute\n" +
            "# on the host at the specified state\n";

    @FXML
    private JFXComboBox<String> stateCombo;

    @FXML
    private JFXTextField fileTextField;

    @FXML
    private JFXTextArea fileData;

    private JFXButton saveButton;

    public HookDialog(Controller controller) {
        super(controller, "/fxml/hook_dialog.fxml");

        setTitle("Hook");

        saveButton = createButton("Save");
        addCancelButton();

        stateCombo.getItems().addAll(
                Arrays.stream(SessionState.values()).map(Enum::name).sorted().collect(Collectors.toList())
        );
        stateCombo.getSelectionModel().select(SessionState.RUNTIME.name());
    }

    public Hook getHook() {
        Hook hook = new Hook();
        hook.setFile(fileTextField.getText());
        hook.setData(fileData.getText());
        SessionState state = SessionState.valueOf(stateCombo.getSelectionModel().getSelectedItem());
        hook.setState(state.getValue());
        hook.setStateDisplay(state.name());
        return hook;
    }

    public void showEditDialog(Hook hook, Runnable editHandler, Runnable cancelHandler) {
        fileData.setText(hook.getData());
        stateCombo.getSelectionModel().select(hook.getState());
        fileTextField.setText(hook.getFile());
        fileTextField.setDisable(true);

        saveButton.setOnAction(event -> {
            logger.info("create hook");
            editHandler.run();
            close();
        });

        show();
    }

    public void showDialog(String fileName, Runnable saveHandler, Runnable cancelHandler) {
        fileData.setText(DEFAULT_DATA);
        stateCombo.getSelectionModel().select(SessionState.RUNTIME.name());
        fileTextField.setText(fileName);
        fileTextField.setDisable(false);

        saveButton.setOnAction(event -> {
            logger.info("create hook");
            saveHandler.run();
            close();
        });

        show();
    }
}
