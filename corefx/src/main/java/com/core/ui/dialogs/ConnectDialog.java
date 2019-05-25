package com.core.ui.dialogs;

import com.core.Controller;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXTextField;
import javafx.fxml.FXML;
import lombok.Data;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

@Data
public class ConnectDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private String address;
    private int port;
    private JFXButton saveButton;
    @FXML JFXTextField addressTextField;
    @FXML JFXTextField portTextField;

    public ConnectDialog(Controller controller) {
        super(controller, "/fxml/connect_dialog.fxml");
        saveButton = createButton("Connect");
        saveButton.setOnAction(event -> {
            address = addressTextField.getText();
            port = Integer.parseInt(portTextField.getText());
            controller.connectToCore(address, port);
            close();
        });
        addCancelButton();
        setTitle("CORE Connection");
        getStage().sizeToScene();
    }

    public void showDialog() {
        addressTextField.setText(address);
        portTextField.setText(Integer.toString(port));
        show();
    }
}
