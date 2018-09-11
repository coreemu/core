package com.core.ui;

import com.core.Controller;
import com.core.data.CoreNode;
import com.core.data.CoreService;
import com.core.rest.ServiceFile;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXComboBox;
import com.jfoenix.controls.JFXTextArea;
import com.jfoenix.controls.JFXTextField;
import javafx.fxml.FXML;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

public class ServiceDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();

    private CoreNode coreNode;
    private CoreService coreService;
    private String serviceName;

    @FXML
    private JFXComboBox<String> executablesComboBox;

    @FXML
    private JFXComboBox<String> dependenciesComboBox;

    @FXML
    private JFXTextField validationModeTextField;

    @FXML
    private JFXTextField validationTimerTextField;

    @FXML
    private JFXComboBox<String> directoriesComboBox;

    @FXML
    private JFXComboBox<String> filesComboBox;

    @FXML
    private JFXTextArea fileTextArea;

    @FXML
    private JFXTextArea startupTextArea;

    @FXML
    private JFXTextArea validateTextArea;

    @FXML
    private JFXTextArea shutdownTextArea;

    public ServiceDialog(Controller controller) {
        super(controller, "/fxml/service_dialog.fxml");

        JFXButton saveButton = createButton("Save");
        saveButton.setOnAction(event -> {
            // retrieve service data
            coreService.setStartup(textToList(startupTextArea.getText()));
            coreService.setValidate(textToList(validateTextArea.getText()));
            coreService.setShutdown(textToList(shutdownTextArea.getText()));

            try {
                getCoreClient().setService(coreNode, serviceName, coreService);

                String fileName = filesComboBox.getSelectionModel().getSelectedItem();
                String data = fileTextArea.getText();
                ServiceFile serviceFile = new ServiceFile(fileName, data);
                getCoreClient().setServiceFile(coreNode, serviceName, serviceFile);
            } catch (IOException ex) {
                logger.error("error setting node service", ex);
            }

            close();
        });
        addCancelButton();

        filesComboBox.valueProperty().addListener((ov, previous, current) -> {
            if (current == null) {
                return;
            }

            try {
                String file = controller.getCoreClient().getServiceFile(coreNode, serviceName, current);
                fileTextArea.setText(file);
            } catch (IOException ex) {
                logger.error("error getting file data", ex);
            }
        });
    }

    private List<String> textToList(String text) {
        return Arrays.stream(text.split("\\n"))
                .filter(x -> !x.isEmpty())
                .collect(Collectors.toList());
    }

    public void showDialog(CoreNode node, String service) {
        setTitle(String.format("%s - %s", node.getName(), service));

        try {
            coreNode = node;

            // node must exist to get file data
            getCoreClient().createNode(node);

            coreService = getCoreClient().getService(node, service);
            logger.info("service dialog: {}", coreService);
            serviceName = service;

            directoriesComboBox.getItems().setAll(coreService.getDirs());
            directoriesComboBox.getSelectionModel().selectFirst();

            executablesComboBox.getItems().setAll(coreService.getExecutables());
            executablesComboBox.getSelectionModel().selectFirst();

            dependenciesComboBox.getItems().setAll(coreService.getDependencies());
            dependenciesComboBox.getSelectionModel().selectFirst();

            validationModeTextField.setText(coreService.getValidationMode());
            validationTimerTextField.setText(coreService.getValidationTimer());

            filesComboBox.getItems().setAll(coreService.getConfigs());
            filesComboBox.getSelectionModel().selectFirst();

            startupTextArea.setText(String.join("\n", coreService.getStartup()));
            validateTextArea.setText(String.join("\n", coreService.getValidate()));
            shutdownTextArea.setText(String.join("\n", coreService.getShutdown()));
        } catch (IOException ex) {
            logger.error("error getting service data", ex);
        }

        show();
    }
}
