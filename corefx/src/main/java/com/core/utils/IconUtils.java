package com.core.utils;

import com.jfoenix.svg.SVGGlyph;
import com.jfoenix.svg.SVGGlyphLoader;
import edu.uci.ics.jung.visualization.LayeredIcon;
import javafx.scene.paint.Paint;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import javax.swing.*;
import java.awt.*;
import java.net.URI;
import java.net.URISyntaxException;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;

public final class IconUtils {
    private static final Logger logger = LogManager.getLogger();
    public static final int ICON_SIZE = 75;
    private static final Map<String, ImageIcon> ICON_MAP = new HashMap<>();

    private IconUtils() {

    }

    public static LayeredIcon getExternalLayeredIcon(String iconPath) {
        ImageIcon imageIcon = ICON_MAP.computeIfAbsent(iconPath, key -> {
            try {
                return new ImageIcon(Paths.get(new URI(iconPath)).toString());
            } catch (URISyntaxException ex) {
                logger.error("error loading icon: {}", iconPath);
                throw new IllegalArgumentException("invalid icon uri: " + iconPath);
            }
        });
        Image image = imageIcon.getImage().getScaledInstance(ICON_SIZE, ICON_SIZE, Image.SCALE_DEFAULT);
        return new LayeredIcon(image);
    }

    public static LayeredIcon getLayeredIcon(String iconPath) {
        ImageIcon imageIcon = ICON_MAP.computeIfAbsent(iconPath, key ->
                new ImageIcon(IconUtils.class.getResource(iconPath)));
        Image image = imageIcon.getImage().getScaledInstance(ICON_SIZE, ICON_SIZE, Image.SCALE_DEFAULT);
        return new LayeredIcon(image);
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

    public static SVGGlyph get(String name, int size, String paint) {
        SVGGlyph svg = get(name);
        if (svg != null) {
            svg.setSize(size);
            svg.setFill(Paint.valueOf(paint));
        }
        return svg;
    }
}
