package com.core;

import com.jfoenix.controls.JFXDecorator;
import com.jfoenix.svg.SVGGlyphLoader;
import javafx.application.Application;
import javafx.application.Platform;
import javafx.fxml.FXMLLoader;
import javafx.scene.Parent;
import javafx.scene.Scene;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;
import javafx.scene.text.Font;
import javafx.stage.Stage;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class Main extends Application {
    private static final Logger logger = LogManager.getLogger();

    @Override
    public void start(Stage window) throws Exception {
        // load svg icons
        SVGGlyphLoader.loadGlyphsFont(getClass().getResourceAsStream("/icons/icomoon_material.svg"),
                "icomoon.svg");
        logger.info("icons: {}", SVGGlyphLoader.getAllGlyphsIDs());

        // load font
        Font.loadFont(getClass().getResourceAsStream("/font/roboto/Roboto-Regular.ttf"), 10);

        // load main fxml
        FXMLLoader loader = new FXMLLoader(getClass().getResource("/fxml/main.fxml"));
        Parent root = loader.load();

        // window decorator
        JFXDecorator decorator = new JFXDecorator(window, root);
        decorator.setCustomMaximize(true);
        decorator.setMaximized(true);
        decorator.setTitle("CORE");
        Image coreIcon = new Image(getClass().getResourceAsStream("/core-icon.png"));
        decorator.setGraphic(new ImageView(coreIcon));
        window.getIcons().add(coreIcon);

        // create scene and set as current scene within window
        Scene scene = new Scene(decorator);
        scene.getStylesheets().add(getClass().getResource("/css/main.css").toExternalForm());
        window.setScene(scene);

        // update controller
        Controller controller = loader.getController();
        controller.setApplication(this);
        controller.setWindow(window);

        // configure window
        window.setOnCloseRequest(event -> {
            logger.info("exiting gui");
            Platform.exit();
            System.exit(0);
        });
        window.setOnShown(windowEvent -> logger.info("stage show event"));
        window.show();
    }

    public static void main(String[] args) {
        launch(args);
    }
}
