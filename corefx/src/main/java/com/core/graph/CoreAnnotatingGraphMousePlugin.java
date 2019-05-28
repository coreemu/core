package com.core.graph;

import com.core.Controller;
import edu.uci.ics.jung.visualization.RenderContext;
import edu.uci.ics.jung.visualization.VisualizationViewer;
import edu.uci.ics.jung.visualization.annotations.AnnotatingGraphMousePlugin;
import edu.uci.ics.jung.visualization.annotations.Annotation;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import javax.swing.*;
import java.awt.*;
import java.awt.event.MouseEvent;
import java.awt.geom.Point2D;
import java.awt.geom.RectangularShape;

public class CoreAnnotatingGraphMousePlugin<V, E> extends AnnotatingGraphMousePlugin<V, E> {
    private static final Logger logger = LogManager.getLogger();
    private final Controller controller;
    private JFrame frame = new JFrame();

    public CoreAnnotatingGraphMousePlugin(Controller controller, RenderContext<V, E> renderContext) {
        super(renderContext);
        this.controller = controller;
        frame.setVisible(false);
        frame.setAlwaysOnTop(true);
    }

    @Override
    public void mouseReleased(MouseEvent e) {
        VisualizationViewer<V, E> vv = (VisualizationViewer) e.getSource();
        if (e.isPopupTrigger()) {
            frame.setLocationRelativeTo(vv);
            String annotationString = JOptionPane.showInputDialog(frame, "Annotation:",
                    "Annotation Label", JOptionPane.PLAIN_MESSAGE);
            if (annotationString != null && annotationString.length() > 0) {
                Point2D p = vv.getRenderContext().getMultiLayerTransformer().inverseTransform(this.down);
                Annotation<String> annotation = new Annotation(annotationString, this.layer,
                        this.annotationColor, this.fill, p);
                this.annotationManager.add(this.layer, annotation);
            }
        } else if (e.getModifiers() == this.modifiers && this.down != null) {
            Point2D out = e.getPoint();
            RectangularShape arect = (RectangularShape) this.rectangularShape.clone();
            arect.setFrameFromDiagonal(this.down, out);
            Shape s = vv.getRenderContext().getMultiLayerTransformer().inverseTransform(arect);
            Annotation<Shape> annotation = new Annotation(s, this.layer, this.annotationColor, this.fill, out);
            this.annotationManager.add(this.layer, annotation);
        }

        this.down = null;
        vv.removePostRenderPaintable(this.lensPaintable);
        vv.repaint();
    }


}
