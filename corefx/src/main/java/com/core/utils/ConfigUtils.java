package com.core.utils;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Properties;

public final class ConfigUtils {
    private static final Logger logger = LogManager.getLogger();
    private static final String DEFAULT_CONFIG = "/config.properties";
    private static final Path CORE_HOME = Paths.get(System.getProperty("user.home"), ".core");
    private static final Path CORE_PROPERTIES = Paths.get(CORE_HOME.toString(), "config.properties");
    private static final Path CORE_XML_DIR = Paths.get(CORE_HOME.toString(), "xml");
    // config fields
    public static final String CORE_REST = "core-rest";
    public static final String CORE_XML_PATH = "xml-path";
    public static final String SHELL_COMMAND = "shell-command";


    private ConfigUtils() {

    }

    public static void save(Properties properties) throws IOException {
        properties.store(new FileOutputStream(CORE_PROPERTIES.toFile()), null);
    }

    public static Properties load() {
        try {
            if (!CORE_HOME.toFile().exists()) {
                logger.info("creating core home directory");
                Files.createDirectory(CORE_HOME);
                Files.createDirectory(CORE_XML_DIR);
            }

            Properties properties = new Properties();
            if (!CORE_PROPERTIES.toFile().exists()) {
                logger.info("creating default configuration");
                Files.copy(ConfigUtils.class.getResourceAsStream(DEFAULT_CONFIG), CORE_PROPERTIES);
                properties.load(new FileInputStream(CORE_PROPERTIES.toFile()));
                properties.setProperty(CORE_XML_PATH, CORE_XML_DIR.toString());
                save(properties);
            } else {
                properties.load(new FileInputStream(CORE_PROPERTIES.toFile()));
            }

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
