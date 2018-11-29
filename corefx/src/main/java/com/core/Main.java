package com.core;

import com.core.utils.ConfigUtils;
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

import java.nio.file.Path;
import java.nio.file.Paths;

public class Main extends Application {
    private static final Path LOG_FILE = Paths.get(System.getProperty("user.home"), ".core", "core.log");

    @Override
    public void start(Stage window) throws Exception {
        // set core dir property for logging
        System.setProperty("core_log", LOG_FILE.toString());

        // check for and create gui home directory
        ConfigUtils.checkForHomeDirectory();

        // load svg icons
        SVGGlyphLoader.loadGlyphsFont(getClass().getResourceAsStream("/icons/icomoon_material.svg"),
                "icomoon.svg");

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
            Platform.exit();
            System.exit(0);
        });
        window.show();
    }

    public static void main(String[] args) {
        launch(args);
    }
}
