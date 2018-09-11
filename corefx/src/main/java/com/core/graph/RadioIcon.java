package com.core.graph;

import com.core.utils.IconUtils;

import javax.swing.*;
import java.awt.*;

public class RadioIcon implements Icon {
    @Override
    public int getIconHeight() {
        return IconUtils.ICON_SIZE;
    }

    @Override
    public int getIconWidth() {
        return IconUtils.ICON_SIZE;
    }

    @Override
    public void paintIcon(Component c, Graphics g, int x, int y) {
        g.setColor(Color.black);
        g.fillOval(x, y, 10, 10);
    }
}
