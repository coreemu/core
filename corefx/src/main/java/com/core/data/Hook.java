package com.core.data;

import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Data;

@Data
public class Hook {
    private String file;
    private Integer state;
    @JsonIgnore
    private String stateDisplay;
    private String data;
}
