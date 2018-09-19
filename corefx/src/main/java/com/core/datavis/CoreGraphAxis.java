package com.core.datavis;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
public class CoreGraphAxis {
    private String label;
    private Double lower;
    private Double upper;
    private Double tick;
}
