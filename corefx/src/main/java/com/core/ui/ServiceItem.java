package com.core.ui;

import com.jfoenix.controls.JFXCheckBox;
import lombok.Data;

@Data
public class ServiceItem {
    private String service;
    private JFXCheckBox checkBox;

    public ServiceItem(String service) {
        this.service = service;
        checkBox = new JFXCheckBox(service);
    }
}
