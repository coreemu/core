package com.core.ui;

import com.jfoenix.controls.JFXSnackbar;
import javafx.scene.layout.StackPane;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public final class Toast {
    private static final Logger logger = LogManager.getLogger();
    private static final long TIMEOUT = 3000;
    private static JFXSnackbar snackbar;

    private Toast() {

    }

    public static void setSnackbarRoot(StackPane stackPane) {
        snackbar = new JFXSnackbar(stackPane);
    }

    private static void toast(String message, String className) {
        JFXSnackbar.SnackbarEvent snackbarEvent = new JFXSnackbar.SnackbarEvent(message,
                className, null, TIMEOUT, false, null);
        snackbar.enqueue(snackbarEvent);
    }

    public static void info(String message) {
        toast(message, "toast-info");
    }

    public static void success(String message) {
        toast(message, "toast-success");
    }

    public static void warning(String message) {
        toast(message, "toast-warning");
    }

    public static void error(String message) {
        error(message, null);
    }

    public static void error(String message, Exception ex) {
        if (ex != null) {
            logger.error(message, ex);
        }
        JFXSnackbar.SnackbarEvent snackbarEvent = new JFXSnackbar.SnackbarEvent(message,
                "toast-error", "X", TIMEOUT, true, event -> snackbar.close());
        snackbar.enqueue(snackbarEvent);
    }
}
