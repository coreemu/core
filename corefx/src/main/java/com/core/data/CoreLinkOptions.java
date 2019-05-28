package com.core.data;

import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
public class CoreLinkOptions {
    private String opaque;
    private Integer session;
    private Double jitter;
    private Integer key;
    private Double mburst;
    private Double mer;
    private Double per;
    private Double bandwidth;
    private Double burst;
    private Double delay;
    private Double dup;
    private Integer unidirectional;
}
