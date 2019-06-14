package com.core.data;

import lombok.Data;

import java.io.File;

@Data
public class MobilityConfig {
    private String file;
    private File scriptFile;
    private Integer refresh;
    private String loop;
    private String autostart;
    private String map;
    private String startScript;
    private String pauseScript;
    private String stopScript;
}
