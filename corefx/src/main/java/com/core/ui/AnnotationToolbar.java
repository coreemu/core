package com.core.ui;

import com.core.graph.NetworkGraph;
import com.core.utils.FxmlUtils;
import com.jfoenix.controls.JFXColorPicker;
import com.jfoenix.controls.JFXComboBox;
import com.jfoenix.controls.JFXToggleButton;
import edu.uci.ics.jung.visualization.annotations.Annotation;
import javafx.event.ActionEvent;
import javafx.fxml.FXML;
import javafx.scene.layout.GridPane;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.awt.*;
import java.awt.geom.Ellipse2D;
import java.awt.geom.RectangularShape;
import java.awt.geom.RoundRectangle2D;

public class AnnotationToolbar extends GridPane {
    private static final Logger logger = LogManager.getLogger();
    private static final String RECTANGLE = "Rectangle";
    private static final String ROUND_RECTANGLE = "RoundRectangle";
    private static final String ELLIPSE = "Ellipse";
    private static final String UPPER_LAYER = "Upper";
    private static final String LOWER_LAYER = "Lower";
    private NetworkGraph graph;
    @FXML private JFXComboBox<String> shapeCombo;
    @FXML private JFXColorPicker colorPicker;
    @FXML private JFXComboBox<String> layerCombo;
    @FXML private JFXToggleButton fillToggle;

    public AnnotationToolbar(NetworkGraph graph) {
        this.graph = graph;
        FxmlUtils.loadRootController(this, "/fxml/annotation_toolbar.fxml");

        // setup annotation shape combo
        shapeCombo.getItems().addAll(RECTANGLE, ROUND_RECTANGLE, ELLIPSE);
        shapeCombo.setOnAction(this::shapeChange);
        shapeCombo.getSelectionModel().selectFirst();

        // setup annotation layer combo
        layerCombo.getItems().addAll(LOWER_LAYER, UPPER_LAYER);
        layerCombo.setOnAction(this::layerChange);
        layerCombo.getSelectionModel().selectFirst();

        // setup annotation color picker
        colorPicker.setOnAction(this::colorChange);
        colorPicker.setValue(javafx.scene.paint.Color.AQUA);
        colorPicker.fireEvent(new ActionEvent());

        // setup annotation toggle fill
        fillToggle.setOnAction(this::fillChange);
    }

    private void fillChange(ActionEvent event) {
        boolean selected = fillToggle.isSelected();
        graph.getGraphMouse().getAnnotatingPlugin().setFill(selected);
    }

    private void colorChange(ActionEvent event) {
        javafx.scene.paint.Color fxColor = colorPicker.getValue();
        java.awt.Color color = new java.awt.Color(
                (float) fxColor.getRed(),
                (float) fxColor.getGreen(),
                (float) fxColor.getBlue(),
                (float) fxColor.getOpacity()
        );
        logger.info("color selected: {}", fxColor);
        graph.getGraphMouse().getAnnotatingPlugin().setAnnotationColor(color);
    }

    private void layerChange(ActionEvent event) {
        String selected = layerCombo.getSelectionModel().getSelectedItem();
        logger.info("annotation layer selected: {}", selected);
        Annotation.Layer layer;
        if (LOWER_LAYER.equals(selected)) {
            layer = Annotation.Layer.LOWER;
        } else {
            layer = Annotation.Layer.UPPER;
        }
        graph.getGraphMouse().getAnnotatingPlugin().setLayer(layer);
    }

    private void shapeChange(ActionEvent event) {
        String selected = shapeCombo.getSelectionModel().getSelectedItem();
        logger.info("annotation shape selected: {}", selected);
        RectangularShape shape = new Rectangle();
        switch (selected) {
            case RECTANGLE:
                shape = new Rectangle();
                break;
            case ROUND_RECTANGLE:
                shape = new RoundRectangle2D.Double(0, 0, 0, 0, 50.0, 50.0);
                break;
            case ELLIPSE:
                shape = new Ellipse2D.Double();
                break;
            default:
                Toast.error("Unknown annotation shape " + selected);
        }
        graph.getGraphMouse().getAnnotatingPlugin().setRectangularShape(shape);
    }
}
