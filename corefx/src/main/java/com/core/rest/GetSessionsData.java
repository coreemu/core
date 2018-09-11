package com.core.rest;

import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
public class GetSessionsData {
    private Integer id;
    private Integer state;
    private Integer nodes;
}
