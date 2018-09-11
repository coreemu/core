package com.core.ui;

import com.core.graph.NetworkGraph;
import com.jfoenix.controls.JFXColorPicker;
import com.jfoenix.controls.JFXComboBox;
import com.jfoenix.controls.JFXToggleButton;
import edu.uci.ics.jung.visualization.annotations.Annotation;
import javafx.fxml.FXML;
import javafx.fxml.FXMLLoader;
import javafx.scene.layout.GridPane;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.awt.*;
import java.awt.geom.Ellipse2D;
import java.awt.geom.RectangularShape;
import java.awt.geom.RoundRectangle2D;
import java.io.IOException;

public class AnnotationToolbar extends GridPane {
    private static final Logger logger = LogManager.getLogger();
    private NetworkGraph graph;

    @FXML
    private JFXComboBox<String> shapeCombo;

    @FXML
    private JFXColorPicker colorPicker;

    @FXML
    private JFXComboBox<String> layerCombo;

    @FXML
    private JFXToggleButton fillToggle;

    public AnnotationToolbar(NetworkGraph graph) {
        this.graph = graph;
        FXMLLoader loader = new FXMLLoader(getClass().getResource("/fxml/annotation_toolbar.fxml"));
        loader.setRoot(this);
        loader.setController(this);

        try {
            loader.load();
        } catch (IOException ex) {
            throw new RuntimeException(ex);
        }

        setup();
    }

    public void setup() {
        // setup annotation shape combo
        shapeCombo.getItems().addAll("Rectangle", "RoundRectangle", "Ellipse");
        shapeCombo.getSelectionModel().select("Rectangle");
        shapeCombo.setOnAction(event -> {
            String selected = shapeCombo.getSelectionModel().getSelectedItem();
            logger.info("annotation shape selected: {}", selected);
            RectangularShape shape = new Rectangle();
            switch (selected) {
                case "Rectangle":
                    shape = new Rectangle();
                    break;
                case "RoundRectangle":
                    shape = new RoundRectangle2D.Double(0, 0, 0, 0, 50.0, 50.0);
                    break;
                case "Ellipse":
                    shape = new Ellipse2D.Double();
                    break;
            }
            graph.getGraphMouse().getAnnotatingPlugin().setRectangularShape(shape);
        });

        // setup annotation layer combo
        layerCombo.getItems().addAll("Lower", "Upper");
        layerCombo.getSelectionModel().select("Lower");
        layerCombo.setOnAction(event -> {
            String selected = layerCombo.getSelectionModel().getSelectedItem();
            logger.info("annotation layer selected: {}", selected);
            Annotation.Layer layer;
            if ("Lower".equals(selected)) {
                layer = Annotation.Layer.LOWER;
            } else {
                layer = Annotation.Layer.UPPER;
            }
            graph.getGraphMouse().getAnnotatingPlugin().setLayer(layer);
        });

        // setup annotation color picker
        colorPicker.setOnAction(event -> {
            javafx.scene.paint.Color fxColor = colorPicker.getValue();
            java.awt.Color color = new java.awt.Color(
                    (float) fxColor.getRed(),
                    (float) fxColor.getGreen(),
                    (float) fxColor.getBlue(),
                    (float) fxColor.getOpacity()
            );
            logger.info("color selected: {}", fxColor);
            graph.getGraphMouse().getAnnotatingPlugin().setAnnotationColor(color);
        });

        // setup annotation toggle fill
        fillToggle.setOnAction(event -> {
            boolean selected = fillToggle.isSelected();
            graph.getGraphMouse().getAnnotatingPlugin().setFill(selected);
        });
    }
}
