package com.core.graph;

import edu.uci.ics.jung.visualization.Layer;
import edu.uci.ics.jung.visualization.VisualizationViewer;

import javax.imageio.ImageIO;
import javax.swing.*;
import java.awt.*;
import java.awt.geom.AffineTransform;
import java.io.IOException;
import java.nio.file.Paths;

public class BackgroundPaintable<V, E> implements VisualizationViewer.Paintable {
    private final ImageIcon imageIcon;
    private final VisualizationViewer<V, E> vv;
    private final String imagePath;

    public BackgroundPaintable(String imagePath, VisualizationViewer<V, E> vv) throws IOException {
        this.imagePath = imagePath;
        Image image = ImageIO.read(Paths.get(imagePath).toFile());
        imageIcon = new ImageIcon(image);
        this.vv = vv;
    }

    public String getImage() {
        return imagePath;
    }

    @Override
    public void paint(Graphics g) {
        Graphics2D g2d = (Graphics2D) g;
        AffineTransform oldXform = g2d.getTransform();
        AffineTransform lat =
                vv.getRenderContext().getMultiLayerTransformer().getTransformer(Layer.LAYOUT).getTransform();
        AffineTransform vat =
                vv.getRenderContext().getMultiLayerTransformer().getTransformer(Layer.VIEW).getTransform();
        AffineTransform at = new AffineTransform();
        at.concatenate(g2d.getTransform());
        at.concatenate(vat);
        at.concatenate(lat);
        g2d.setTransform(at);
        g.drawImage(imageIcon.getImage(), 0, 0,
                imageIcon.getIconWidth(), imageIcon.getIconHeight(), vv);
        g2d.setTransform(oldXform);
    }

    @Override
    public boolean useTransform() {
        return false;
    }
}
