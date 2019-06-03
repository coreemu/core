package com.core.client.rest;

import lombok.Data;

@Data
public class WlanConfig {
    private String range;
    private String bandwidth;
    private String jitter;
    private String delay;
    private String error;
}
