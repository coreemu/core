package com.core.utils;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;
import java.util.Properties;

public final class ConfigUtils {
    private static final Logger logger = LogManager.getLogger();
    private static final String DEFAULT_CONFIG = "/config.properties";

    private ConfigUtils() {

    }

    public static Properties load() {
        String filePath = System.getProperty("config.file", DEFAULT_CONFIG);
        logger.info("loading config file: {}", filePath);

        try {
            Properties properties = new Properties();
            properties.load(ConfigUtils.class.getResourceAsStream(filePath));

            // override values if provided
            for (String key : properties.stringPropertyNames()) {
                String value = System.getProperty(key);
                if (value != null) {
                    logger.info("command line config: {} - {}", key, value);
                    properties.setProperty(key, value);
                }
            }

            return properties;
        } catch (IOException ex) {
            logger.error("error reading config file");
            throw new RuntimeException("configuration file did not exist");
        }
    }
}
