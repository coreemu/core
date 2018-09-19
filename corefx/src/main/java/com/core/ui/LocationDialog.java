package com.core.ui;

import com.core.Controller;
import com.core.data.LocationConfig;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXTextField;
import com.jfoenix.validation.DoubleValidator;
import javafx.fxml.FXML;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;

public class LocationDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();

    @FXML
    private JFXTextField scaleTextField;

    @FXML
    private JFXTextField xTextField;

    @FXML
    private JFXTextField yTextField;

    @FXML
    private JFXTextField latTextField;

    @FXML
    private JFXTextField lonTextField;

    @FXML
    private JFXTextField altTextField;

    private JFXButton saveButton;

    public LocationDialog(Controller controller) {
        super(controller, "/fxml/location_dialog.fxml");
        setTitle("Location Configuration");
        saveButton = createButton("Save");
        saveButton.setOnAction(event -> {
            boolean result = scaleTextField.validate();
            if (!result) {
                return;
            }

            LocationConfig config = new LocationConfig();
            config.setScale(getDouble(scaleTextField));
            config.getPosition().setX(getDouble(xTextField));
            config.getPosition().setY(getDouble(yTextField));
            config.getLocation().setLatitude(getDouble(latTextField));
            config.getLocation().setLongitude(getDouble(lonTextField));
            config.getLocation().setAltitude(getDouble(altTextField));
            try {
                getCoreClient().setLocationConfig(config);
                close();
            } catch (IOException ex) {
                Toast.error("error setting location config", ex);
            }
        });
        addCancelButton();

        DoubleValidator validator = new DoubleValidator();
        scaleTextField.getValidators().add(validator);
    }

    public Double getDouble(JFXTextField textField) {
        return Double.parseDouble(textField.getText());
    }

    public void showDialog() {
        try {
            LocationConfig config = getCoreClient().getLocationConfig();
            scaleTextField.setText(config.getScale().toString());
            xTextField.setText(config.getPosition().getX().toString());
            yTextField.setText(config.getPosition().getY().toString());
            latTextField.setText(config.getLocation().getLatitude().toString());
            lonTextField.setText(config.getLocation().getLongitude().toString());
            altTextField.setText(config.getLocation().getAltitude().toString());
            show();
        } catch (IOException ex) {
            Toast.error("error getting location config", ex);
        }
    }
}
