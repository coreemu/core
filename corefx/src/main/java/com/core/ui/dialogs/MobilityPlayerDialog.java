package com.core.ui.dialogs;

import com.core.Controller;
import com.core.data.CoreNode;
import com.core.data.MobilityConfig;
import com.core.data.SessionState;
import com.core.ui.Toast;
import com.core.utils.IconUtils;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXProgressBar;
import javafx.animation.KeyFrame;
import javafx.animation.KeyValue;
import javafx.animation.Timeline;
import javafx.application.Platform;
import javafx.fxml.FXML;
import javafx.scene.control.Label;
import javafx.stage.Modality;
import javafx.util.Duration;
import lombok.Data;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;

@Data
public class MobilityPlayerDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private static final int ICON_SIZE = 20;
    private static final String ICON_FILL = "white";
    @FXML private Label label;
    @FXML private JFXButton playButton;
    @FXML private JFXButton pauseButton;
    @FXML private JFXButton stopButton;
    @FXML private JFXProgressBar progressBar;
    private final CoreNode node;
    private MobilityConfig mobilityConfig;

    public MobilityPlayerDialog(Controller controller, CoreNode node) {
        super(controller, "/fxml/mobility_player.fxml", Modality.NONE);
        this.node = node;

        playButton.setGraphic(IconUtils.get("play_arrow", ICON_SIZE, ICON_FILL));
        playButton.setOnAction(event -> action("start"));
        pauseButton.setGraphic(IconUtils.get("pause", ICON_SIZE, ICON_FILL));
        pauseButton.setOnAction(event -> action("pause"));
        stopButton.setGraphic(IconUtils.get("stop", ICON_SIZE, ICON_FILL));
        stopButton.setOnAction(event -> action("stop"));

        addCancelButton();
        setTitle(String.format("%s Mobility Script", node.getName()));
        getStage().sizeToScene();
    }

    public void event(SessionState state, Integer start, Integer end) {
        Platform.runLater(() -> {
            playButton.setDisable(false);
            stopButton.setDisable(false);

            switch (state) {
                case START:
                    playButton.setDisable(true);
                    progressBar.setProgress(0);
                    Timeline timeline = new Timeline();
                    KeyValue keyValue = new KeyValue(progressBar.progressProperty(), 1.0);
                    KeyFrame keyFrame = new KeyFrame(new Duration(end * 1000), keyValue);
                    timeline.getKeyFrames().add(keyFrame);
                    timeline.play();
                    break;
                case STOP:
                    stopButton.setDisable(true);
                    break;
            }
        });
    }

    private void action(String action) {
        try {
            getCoreClient().mobilityAction(node, action);
        } catch (IOException ex) {
            Toast.error(String.format("mobility error: %s", action), ex);
        }
    }

    public void showDialog(MobilityConfig mobilityConfig) {
        this.label.setText(mobilityConfig.getFile());
        this.mobilityConfig = mobilityConfig;
        show();
    }
}
