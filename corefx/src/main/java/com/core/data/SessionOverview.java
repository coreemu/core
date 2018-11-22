package com.core.data;

import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
public class SessionOverview {
    private Integer id;
    private Integer state;
    private Integer nodes = 0;
    private String url;
}
