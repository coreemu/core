package com.core.utils;

import com.jfoenix.svg.SVGGlyph;
import com.jfoenix.svg.SVGGlyphLoader;
import edu.uci.ics.jung.visualization.LayeredIcon;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import javax.swing.*;
import java.awt.*;
import java.util.HashMap;
import java.util.Map;

public final class IconUtils {
    private static final Logger logger = LogManager.getLogger();
    public static final int ICON_SIZE = 75;
    private static final Map<String, LayeredIcon> ICON_MAP = new HashMap<>();

    private IconUtils() {

    }

    public static LayeredIcon getIcon(String iconPath) {
        return ICON_MAP.computeIfAbsent(iconPath, key -> {
            ImageIcon imageIcon = new ImageIcon(IconUtils.class.getResource(iconPath));
            Image image = imageIcon.getImage().getScaledInstance(ICON_SIZE, ICON_SIZE, Image.SCALE_DEFAULT);
            return new LayeredIcon(image);
        });
    }

    public static SVGGlyph get(String name) {
        SVGGlyph svg = null;
        try {
            svg = SVGGlyphLoader.getIcoMoonGlyph("icomoon.svg." + name);
        } catch (Exception ex) {
            logger.error("error loading icon: {}", name, ex);
        }
        return svg;
    }
}
