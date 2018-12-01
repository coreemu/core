package com.core.ui.dialogs;

import com.core.Controller;
import com.core.data.CoreNode;
import com.core.ui.Toast;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXTextArea;
import com.jfoenix.controls.JFXTextField;
import javafx.concurrent.Task;
import javafx.fxml.FXML;
import lombok.Data;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

@Data
public class TerminalDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private String address;
    private int port;
    private JFXButton saveButton;
    @FXML JFXTextArea outputTextArea;
    @FXML JFXTextField commandTextField;
    private CoreNode node;

    public TerminalDialog(Controller controller) {
        super(controller, "/fxml/terminal_dialog.fxml");
        commandTextField.setOnAction(event -> {
            String command = commandTextField.getText();
            addOutput(String.format("$> %s", command));
            new Thread(new CommandTask(command)).start();
            commandTextField.clear();
        });
    }


    private class CommandTask extends Task<String> {
        private String command;

        CommandTask(String command) {
            this.command = command;
        }

        @Override
        protected String call() throws Exception {
            return getCoreClient().nodeCommand(node, command);
        }

        @Override
        protected void succeeded() {
            addOutput(getValue());
        }

        @Override
        protected void failed() {
            Toast.error("Failed sending terminal command", new RuntimeException(getException()));
        }
    }

    private void addOutput(String output) {
        outputTextArea.appendText(String.format("%s%n", output));
    }

    public void showDialog(CoreNode node) {
        this.node = node;
        setTitle(String.format("%s Pseudo Terminal", node.getName()));
        outputTextArea.setText("");
        commandTextField.setText("");
        commandTextField.requestFocus();
        show();
    }
}
