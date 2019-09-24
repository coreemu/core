package com.core.data;

import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
public class CoreLinkOptions {
    private String opaque;
    private Integer session;
    private Integer jitter;
    private Integer key;
    private Integer mburst;
    private Integer mer;
    private Double per;
    private Integer bandwidth;
    private Integer burst;
    private Integer delay;
    private Integer dup;
    private Boolean unidirectional;
}
