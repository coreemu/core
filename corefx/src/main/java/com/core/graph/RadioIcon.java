package com.core.graph;

import com.core.utils.IconUtils;
import lombok.Data;

import javax.swing.*;
import java.awt.*;

@Data
public class RadioIcon implements Icon {
    private long wiressLinks = 0;

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
        for (int i = 0; i < wiressLinks; i++) {
            g.fillOval(x, y, 10, 10);
            x += 15;
        }
    }
}
