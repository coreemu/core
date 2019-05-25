package com.core.utils;

import javafx.fxml.FXMLLoader;

import java.io.IOException;

public final class FxmlUtils {
    private FxmlUtils() {
    }

    public static void loadRootController(Object obj, String fxmlPath) {
        FXMLLoader loader = new FXMLLoader(FxmlUtils.class.getResource(fxmlPath));
        loader.setRoot(obj);
        loader.setController(obj);

        try {
            loader.load();
        } catch (IOException ex) {
            throw new RuntimeException(ex);
        }
    }
}
