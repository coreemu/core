package com.core.ui.textfields;

import javafx.scene.control.TextFormatter;

import java.util.function.UnaryOperator;
import java.util.regex.Pattern;

public class DoubleFilter implements UnaryOperator<TextFormatter.Change> {
    private static final Pattern DIGIT_PATTERN = Pattern.compile("\\d*\\.?\\d*");

    @Override
    public TextFormatter.Change apply(TextFormatter.Change change) {
        return DIGIT_PATTERN.matcher(change.getText()).matches() ? change : null;
    }
}
