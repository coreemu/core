package com.core.data;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class CoreService {
    private List<String> executables = new ArrayList<>();
    private List<String> dependencies = new ArrayList<>();
    private List<String> dirs = new ArrayList<>();
    private List<String> configs = new ArrayList<>();
    private List<String> startup = new ArrayList<>();
    private List<String> validate = new ArrayList<>();
    private String validationMode;
    private String validationTimer;
    private List<String> shutdown = new ArrayList<>();
    private String meta;
}
