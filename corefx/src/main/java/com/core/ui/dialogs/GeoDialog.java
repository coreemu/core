package com.core.ui.dialogs;

import com.core.Controller;
import com.jfoenix.controls.JFXButton;
import javafx.fxml.FXML;
import javafx.scene.web.WebView;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class GeoDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    @FXML private WebView webView;
    @FXML JFXButton button;

    public GeoDialog(Controller controller) {
        super(controller, "/fxml/geo_dialog.fxml");
        setTitle("Geo Display");
        addCancelButton();
        webView.getEngine().load(getClass().getResource("/html/geo.html").toExternalForm());
        button.setOnAction(event -> {
            webView.getEngine().executeScript("randomMarker();");
        });
    }

    public void showDialog() {
        show();
    }
}
