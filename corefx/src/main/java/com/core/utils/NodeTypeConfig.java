package com.core.utils;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@EqualsAndHashCode(onlyExplicitlyIncluded = true)
@NoArgsConstructor
@AllArgsConstructor
public class NodeTypeConfig {
    @EqualsAndHashCode.Include
    private String model;
    private String display;
    private String icon;
    private List<String> services;
}
