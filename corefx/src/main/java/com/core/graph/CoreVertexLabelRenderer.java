package com.core.graph;

import edu.uci.ics.jung.visualization.renderers.DefaultVertexLabelRenderer;

import javax.swing.*;
import javax.swing.border.EmptyBorder;
import java.awt.*;

public class CoreVertexLabelRenderer extends DefaultVertexLabelRenderer {
    private Color foregroundColor = Color.WHITE;
    private Color backgroundColor = Color.BLACK;

    CoreVertexLabelRenderer() {
        super(Color.YELLOW);
    }

    public void setColors(Color foregroundColor, Color backgroundColor) {
        this.foregroundColor = foregroundColor;
        this.backgroundColor = backgroundColor;
    }

    @Override
    public <V> Component getVertexLabelRendererComponent(JComponent vv, Object value, Font font, boolean isSelected, V vertex) {
        super.setForeground(foregroundColor);
        if (isSelected) {
            this.setForeground(this.pickedVertexLabelColor);
        }

        super.setBackground(backgroundColor);
        if (font != null) {
            this.setFont(font);
        } else {
            this.setFont(vv.getFont());
        }

        this.setIcon(null);
        EmptyBorder padding = new EmptyBorder(5, 5, 5, 5);
        this.setBorder(padding);
        this.setValue(value);
        setFont(getFont().deriveFont(Font.BOLD));
        return this;
    }
}
