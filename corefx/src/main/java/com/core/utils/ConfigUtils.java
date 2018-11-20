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
    private static final Path HOME = Paths.get(System.getProperty("user.home"), ".core");
    private static final Path PROPERTIES_FILE = Paths.get(HOME.toString(), "config.properties");
    private static final Path XML_DIR = Paths.get(HOME.toString(), "xml");
    private static final Path MOBILITY_DIR = Paths.get(HOME.toString(), "mobility");
    // config fields
    public static final String REST_URL = "core-rest";
    public static final String XML_PATH = "xml-path";
    public static final String MOBILITY_PATH = "mobility-path";
    public static final String SHELL_COMMAND = "shell-command";


    private ConfigUtils() {

    }

    public static void save(Properties properties) throws IOException {
        properties.store(new FileOutputStream(PROPERTIES_FILE.toFile()), null);
    }

    public static Properties load() {
        try {
            if (!HOME.toFile().exists()) {
                logger.info("creating core home directory");
                Files.createDirectory(HOME);
                Files.createDirectory(XML_DIR);
                Files.createDirectory(MOBILITY_DIR);
            }

            Properties properties = new Properties();
            if (!PROPERTIES_FILE.toFile().exists()) {
                logger.info("creating default configuration");
                Files.copy(ConfigUtils.class.getResourceAsStream(DEFAULT_CONFIG), PROPERTIES_FILE);
                properties.load(new FileInputStream(PROPERTIES_FILE.toFile()));
                properties.setProperty(XML_PATH, XML_DIR.toString());
                properties.setProperty(MOBILITY_PATH, MOBILITY_DIR.toString());
                save(properties);
            } else {
                properties.load(new FileInputStream(PROPERTIES_FILE.toFile()));
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
