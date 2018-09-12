package com.core.data;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
public class MobilityConfig {
    private String file;
    @JsonProperty("refresh_ms")
    private Integer refresh;
    private String loop;
    private String autostart;
    private String map;
    @JsonProperty("script_start")
    private String startScript;
    @JsonProperty("script_pause")
    private String pauseScript;
    @JsonProperty("script_stop")
    private String stopScript;
}
