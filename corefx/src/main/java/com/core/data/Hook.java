package com.core.data;

import lombok.Data;

@Data
public class Hook {
    private String file;
    private Integer state;
    private String stateDisplay;
    private String data;
}
