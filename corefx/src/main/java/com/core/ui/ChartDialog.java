package com.core.ui;

import com.core.Controller;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXComboBox;
import javafx.application.Platform;
import javafx.fxml.FXML;
import javafx.scene.chart.*;
import javafx.scene.layout.Pane;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

public class ChartDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private final AtomicBoolean running = new AtomicBoolean(false);
    private final Random numbers = new Random();
    private final List<String> chartNames = Arrays.asList("Name 1", "Name 2", "Name 3", "Name 4", "Name 5");

    @FXML
    private JFXComboBox<String> chartCombo;

    @FXML
    private Pane chartPane;

    @FXML
    private JFXButton stopButton;

    public ChartDialog(Controller controller) {
        super(controller, "/fxml/chart_dialog.fxml");
        addCancelButton();

        chartCombo.getItems().addAll("pie", "line", "area", "bar", "scatter", "bubble");
        chartCombo.getSelectionModel().selectedItemProperty().addListener((ov, prev, curr) -> {
            if (curr == null) {
                return;
            }

            running.set(false);
            switch (curr) {
                case "pie":
                    pieChart();
                    break;
                case "line":
                    lineChart();
                    break;
                case "area":
                    areaChart();
                    break;
                case "bar":
                    barChart();
                    break;
                case "scatter":
                    scatterChart();
                    break;
                case "bubble":
                    bubbleChart();
                    break;
            }
        });

        stopButton.setOnAction(event -> running.set(false));
        chartCombo.getSelectionModel().selectFirst();
    }

    private void bubbleChart() {
        NumberAxis xAxis = new NumberAxis("X Axis", 0, 100, 1);
        NumberAxis yAxis = new NumberAxis("Y Axis", 0, 100, 1);
        BubbleChart<Number, Number> chart = new BubbleChart<>(xAxis, yAxis);
        XYChart.Series<Number, Number> series = new XYChart.Series<>();
        series.setName("Bubble Series Data");
        chart.getData().add(series);
        chart.setTitle("Bubble Chart");
        chart.prefHeightProperty().bind(chartPane.heightProperty());
        chart.prefWidthProperty().bind(chartPane.widthProperty());
        chartPane.getChildren().clear();
        chartPane.getChildren().add(chart);
        running.set(true);
        new Thread(() -> {
            while (running.get()) {
                try {
                    Integer x = numbers.nextInt(100);
                    Integer y = numbers.nextInt(100);
                    Integer weight = numbers.nextInt(10);
                    Platform.runLater(() -> series.getData().add(new XYChart.Data<>(x, y, weight)));
                    Thread.sleep(1000);
                } catch (Exception ex) {
                    logger.error("error adding data", ex);
                }
            }
        }).start();
    }

    private void scatterChart() {
        NumberAxis xAxis = new NumberAxis("X Axis", 0, 100, 1);
        NumberAxis yAxis = new NumberAxis("Y Axis", 0, 100, 1);
        ScatterChart<Number, Number> chart = new ScatterChart<>(xAxis, yAxis);
        XYChart.Series<Number, Number> series = new XYChart.Series<>();
        series.setName("Scatter Series Data");
        chart.getData().add(series);
        chart.setTitle("Scatter Chart");
        chart.prefHeightProperty().bind(chartPane.heightProperty());
        chart.prefWidthProperty().bind(chartPane.widthProperty());
        chartPane.getChildren().clear();
        chartPane.getChildren().add(chart);
        running.set(true);
        new Thread(() -> {
            while (running.get()) {
                try {
                    Integer x = numbers.nextInt(100);
                    Integer y = numbers.nextInt(100);
                    Platform.runLater(() -> series.getData().add(new XYChart.Data<>(x, y)));
                    Thread.sleep(1000);
                } catch (Exception ex) {
                    logger.error("error adding data", ex);
                }
            }
        }).start();
    }

    private void areaChart() {
        NumberAxis xAxis = new NumberAxis("X Axis", 0, 100, 1);
        NumberAxis yAxis = new NumberAxis("Y Axis", 0, 100, 1);
        AreaChart<Number, Number> chart = new AreaChart<>(xAxis, yAxis);
        XYChart.Series<Number, Number> series = new XYChart.Series<>();
        series.setName("Area Series Data");
        chart.getData().add(series);
        chart.setTitle("Area Chart");
        chart.prefHeightProperty().bind(chartPane.heightProperty());
        chart.prefWidthProperty().bind(chartPane.widthProperty());
        chartPane.getChildren().clear();
        chartPane.getChildren().add(chart);
        running.set(true);
        new Thread(() -> {
            while (running.get()) {
                try {
                    Integer x = numbers.nextInt(100);
                    Integer y = numbers.nextInt(100);
                    Platform.runLater(() -> series.getData().add(new XYChart.Data<>(x, y)));
                    Thread.sleep(1000);
                } catch (Exception ex) {
                    logger.error("error adding data", ex);
                }
            }
        }).start();
    }

    private void lineChart() {
        NumberAxis xAxis = new NumberAxis("X Axis", 0, 100, 1);
        NumberAxis yAxis = new NumberAxis("Y Axis", 0, 100, 1);
        LineChart<Number, Number> chart = new LineChart<>(xAxis, yAxis);
        XYChart.Series<Number, Number> series = new XYChart.Series<>();
        series.setName("Line Series Data");
        chart.getData().add(series);
        chart.setTitle("Line Chart");
        chart.prefHeightProperty().bind(chartPane.heightProperty());
        chart.prefWidthProperty().bind(chartPane.widthProperty());
        chartPane.getChildren().clear();
        chartPane.getChildren().add(chart);
        running.set(true);
        new Thread(() -> {
            while (running.get()) {
                try {
                    Integer x = numbers.nextInt(100);
                    Integer y = numbers.nextInt(100);
                    Platform.runLater(() -> series.getData().add(new XYChart.Data<>(x, y)));
                    Thread.sleep(1000);
                } catch (Exception ex) {
                    logger.error("error adding data", ex);
                }
            }
        }).start();
    }

    private void pieChart() {
        PieChart chart = new PieChart();
        chart.setTitle("Pie Chart");
        chart.prefHeightProperty().bind(chartPane.heightProperty());
        chart.prefWidthProperty().bind(chartPane.widthProperty());
        chartPane.getChildren().clear();
        chartPane.getChildren().add(chart);
        running.set(true);
        Map<String, PieChart.Data> pieMap = new HashMap<>();
        new Thread(() -> {
            while (running.get()) {
                try {
                    String name = chartNames.get(numbers.nextInt(chartNames.size()));
                    Integer y = numbers.nextInt(100);
                    Platform.runLater(() -> {
                        PieChart.Data data = pieMap.get(name);
                        if (data != null) {
                            data.setPieValue(y);
                        } else {
                            data = new PieChart.Data(name, y);
                            chart.getData().add(data);
                            pieMap.put(name, data);
                        }
                    });
                    Thread.sleep(1000);
                } catch (Exception ex) {
                    logger.error("error adding data", ex);
                }
            }
        }).start();
    }

    private void barChart() {
        CategoryAxis xAxis = new CategoryAxis();
        xAxis.setLabel("X Axis");
        xAxis.getCategories().add("My Ctageory");
        NumberAxis yAxis = new NumberAxis("Y Axis", 0, 100, 1);
        BarChart<String, Number> chart = new BarChart<>(xAxis, yAxis);
        XYChart.Series<String, Number> series = new XYChart.Series<>();
        series.setName("Bar Chart Series");
        chart.getData().add(series);
        chart.setTitle("Bar Chart");
        chart.prefHeightProperty().bind(chartPane.heightProperty());
        chart.prefWidthProperty().bind(chartPane.widthProperty());
        chartPane.getChildren().clear();
        chartPane.getChildren().add(chart);
        running.set(true);
        Map<String, XYChart.Data<String, Number>> barMap = new HashMap<>();
        new Thread(() -> {
            while (running.get()) {
                try {
                    String name = chartNames.get(numbers.nextInt(chartNames.size()));
                    Integer y = numbers.nextInt(100);
                    Platform.runLater(() -> {
                        XYChart.Data<String, Number> data = barMap.get(name);
                        if (data != null) {
                            data.setYValue(y);
                        } else {
                            data = new XYChart.Data<>(name, y);
                            series.getData().add(data);
                            barMap.put(name, data);
                        }
                    });
                    Thread.sleep(1000);
                } catch (Exception ex) {
                    logger.error("error adding data", ex);
                }
            }
        }).start();
    }


    public void showDialog() {
        chartCombo.getSelectionModel().selectFirst();
    }
}
