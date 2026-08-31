#!/usr/bin/env Rscript

# G5 figure and table export. This script reads only the frozen G4 summary;
# it does not access case-level files or recompute any statistic.

suppressPackageStartupMessages({
  library(jsonlite)
  library(ggplot2)
  library(patchwork)
  library(grid)
  library(ragg)
  library(svglite)
})

root <- normalizePath(getwd(), mustWork = TRUE)
summary_path <- file.path(root, "data", "frozen_g4_summary_public.json")
out_dir <- root
fig_dir <- file.path(out_dir, "figures")
table_dir <- file.path(out_dir, "tables")
dir.create(fig_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(table_dir, recursive = TRUE, showWarnings = FALSE)

g4 <- fromJSON(summary_path, simplifyVector = FALSE)

theme_set(theme_classic(base_size = 9, base_family = "sans") +
  theme(
    axis.line = element_line(linewidth = 0.35, colour = "black"),
    axis.ticks = element_line(linewidth = 0.35, colour = "black"),
    panel.grid = element_blank(),
    plot.title = element_text(size = 10, face = "bold", hjust = 0),
    plot.subtitle = element_text(size = 8, colour = "#444444"),
    axis.title = element_text(size = 8.5),
    axis.text = element_text(size = 8),
    strip.text = element_text(size = 8, face = "bold"),
    legend.title = element_text(size = 8),
    legend.text = element_text(size = 7.5),
    plot.margin = margin(8, 10, 8, 8)
  ))

save_pub <- function(plot, stem, width_mm = 183, height_mm = 115, dpi = 600) {
  w <- width_mm / 25.4
  h <- height_mm / 25.4
  svglite::svglite(file.path(fig_dir, paste0(stem, ".svg")), width = w, height = h)
  print(plot)
  dev.off()
  grDevices::pdf(file.path(fig_dir, paste0(stem, ".pdf")), width = w, height = h, family = "Helvetica", useDingbats = FALSE)
  print(plot)
  dev.off()
  ragg::agg_tiff(file.path(fig_dir, paste0(stem, ".tiff")), width = w, height = h, units = "in", res = dpi, compression = "lzw")
  print(plot)
  dev.off()
  ragg::agg_png(file.path(fig_dir, paste0(stem, ".png")), width = w, height = h, units = "in", res = 300)
  print(plot)
  dev.off()
}

strata <- c("R2_TEST", "SOOP", "R3_NEW")
labels <- c(R2_TEST = "R2_TEST", SOOP = "SOOP", R3_NEW = "R3_NEW")
roles <- c(R2_TEST = "Multicenter reference", SOOP = "Single-source stress test", R3_NEW = "Multicenter shift stratum")
counts <- c(R2_TEST = 288, SOOP = 157, R3_NEW = 317)
centers <- c(R2_TEST = 24, SOOP = 1, R3_NEW = 26)

# Figure 1: cohort composition, QC, and decision workflow (schematic-led composite).
cohort_df <- data.frame(
  stratum = factor(strata, levels = strata),
  cases = unname(counts[strata]),
  centers = unname(centers[strata]),
  descriptor = c("24 centers", "1 source", "26 centers")
)
cohort_panel <- ggplot(cohort_df, aes(cases, stratum, fill = stratum)) +
  geom_col(width = 0.58, colour = "#25343B", linewidth = 0.25) +
  geom_text(aes(x = cases / 2, label = sprintf("n = %d\n%s", cases, descriptor)), hjust = 0.5, size = 2.55, lineheight = 0.9, colour = "white") +
  scale_fill_manual(values = c(R2_TEST = "#1C6070", SOOP = "#A36119", R3_NEW = "#8D3E3E"), guide = "none") +
  scale_x_continuous(limits = c(0, 440), breaks = c(0, 100, 200, 300, 400), expand = expansion(mult = c(0, 0.02))) +
  labs(title = "Formal cohort composition", subtitle = "762 cases; Pilot-36 excluded; one release family", x = "Cases", y = NULL) +
  theme(plot.title = element_text(size = 9, face = "bold"), axis.text.y = element_text(size = 8))

qc_df <- data.frame(
  stratum = rep(strata, 4),
  metric = rep(c("Inference failure", "Scoring failure", "Empty prediction", "Empty ground truth"), each = length(strata)),
  value = c(
    rep(0, 3), rep(0, 3),
    100 * c(g4$strata$R2_TEST$empty_prediction_rate, g4$strata$SOOP$empty_prediction_rate, g4$strata$R3_NEW$empty_prediction_rate),
    100 * c(g4$strata$R2_TEST$empty_ground_truth_rate, g4$strata$SOOP$empty_ground_truth_rate, g4$strata$R3_NEW$empty_ground_truth_rate)
  )
)
qc_df$stratum <- factor(qc_df$stratum, levels = strata)
qc_df$metric <- factor(qc_df$metric, levels = rev(c("Inference failure", "Scoring failure", "Empty prediction", "Empty ground truth")))
qc_panel <- ggplot(qc_df, aes(stratum, metric, fill = value)) +
  geom_tile(colour = "white", linewidth = 0.45) +
  geom_text(aes(label = sprintf("%.2f%%", value)), size = 2.6, colour = "#17242B") +
  scale_fill_gradient(low = "#E8EEF5", high = "#A85E56", limits = c(0, 6), guide = "none") +
  labs(title = "Execution and output QC", subtitle = "All 762 formal cases were scored", x = NULL, y = NULL) +
  theme(plot.title = element_text(size = 9, face = "bold"), axis.text.x = element_text(size = 7.5), axis.text.y = element_text(size = 7.5))

box_df <- data.frame(
  x = c(1, 1, 1, 1),
  y = c(4, 3, 2, 1),
  title = c("Frozen cohort", "Five-fold inference", "Official scoring", "G4 decision"),
  detail = c("762 cases; Pilot-36 excluded", "folds 0-4; equal softmax mean; TTA off", "array-index masks; no resampling", "delta, CI, and p criteria jointly"),
  fill = c("#E8EEF5", "#E6F2EF", "#F7EEE0", "#F4E5E5")
)
workflow <- ggplot(box_df, aes(x, y)) +
  geom_segment(data = data.frame(y = c(3.58, 2.58, 1.58), yend = c(3.42, 2.42, 1.42)),
               aes(x = 1, xend = 1, y = y, yend = yend), arrow = arrow(length = unit(0.12, "cm")), linewidth = 0.45, colour = "#3C4A52") +
  geom_label(aes(label = title, fill = fill), colour = "#15232B", fontface = "bold", size = 3.1, linewidth = 0.3, label.padding = unit(0.18, "lines"), show.legend = FALSE) +
  geom_text(aes(label = detail), nudge_y = -0.22, size = 2.7, colour = "#34434B") +
  annotate("text", x = 2.25, y = 4, label = "R2_TEST\n288 cases / 24 centers", hjust = 0, size = 3.1, colour = "#1C6070") +
  annotate("text", x = 2.25, y = 3, label = "SOOP\n157 cases / 1 source", hjust = 0, size = 3.1, colour = "#A36119") +
  annotate("text", x = 2.25, y = 2, label = "R3_NEW\n317 cases / 26 centers", hjust = 0, size = 3.1, colour = "#8D3E3E") +
  annotate("text", x = 2.25, y = 1, label = "G4: FAILED\nCI included 0; p = 0.05099", hjust = 0, size = 3.1, fontface = "bold", colour = "#8D3E3E") +
  annotate("text", x = 3.55, y = 4.05, label = "record-level audit\n0 cross-stratum case-ID overlap\n4 shared R2/R3 center labels", hjust = 0, size = 2.65, lineheight = 0.92, colour = "#4B5559") +
  coord_cartesian(xlim = c(0.55, 5.7), ylim = c(0.55, 4.45), clip = "off") +
  scale_fill_identity() +
  labs(title = "Prespecified external evaluation and G4 decision pathway", subtitle = "All design elements and denominators were frozen before v1.2 prediction") +
  theme(axis.title = element_blank(), axis.text = element_blank(), axis.ticks = element_blank(), axis.line = element_blank())
fig1 <- cohort_panel + qc_panel + workflow +
  plot_layout(design = "AB\nCC", heights = c(1, 1.15)) +
  plot_annotation(tag_levels = "a") &
  theme(plot.tag = element_text(size = 8, face = "bold"))
save_pub(fig1, "Figure_1_cohort_and_gate_workflow", width_mm = 183, height_mm = 135)

# Figure 2: primary endpoint, contrast, and frozen inferential boundary.
center_df <- data.frame(
  stratum = factor(c("R2_TEST", "R3_NEW"), levels = c("R2_TEST", "R3_NEW")),
  f1 = c(g4$primary$R2_TEST$center_macro_lesion_f1, g4$primary$R3_NEW$center_macro_lesion_f1),
  n_centers = c(g4$primary$R2_TEST$n_centers, g4$primary$R3_NEW$n_centers)
)
contrast_df <- data.frame(
  contrast = "R2_TEST - R3_NEW",
  estimate = g4$primary$observed_R2_TEST_minus_R3_NEW,
  low = g4$primary$percentile_95_ci[[1]],
  high = g4$primary$percentile_95_ci[[2]]
)
p_left <- ggplot(center_df, aes(stratum, f1, fill = stratum)) +
  geom_col(width = 0.58, colour = "#25343B", linewidth = 0.25) +
  geom_text(aes(label = sprintf("%.3f\nn = %d centers", f1, n_centers)), vjust = -0.28, size = 3.0, lineheight = 0.9) +
  scale_fill_manual(values = c(R2_TEST = "#1C6070", R3_NEW = "#8D3E3E"), guide = "none") +
  scale_y_continuous(limits = c(0, 0.65), expand = expansion(mult = c(0, 0.06))) +
  labs(title = "Center-macro lesion-wise F1", subtitle = "Bars show frozen stratum estimates", x = NULL, y = "F1") +
  theme(plot.title = element_text(size = 9, face = "bold"))
p_right <- ggplot(contrast_df, aes(contrast, estimate)) +
  geom_hline(yintercept = 0, linewidth = 0.4, colour = "#333333") +
  geom_hline(yintercept = 0.05, linewidth = 0.45, linetype = "dashed", colour = "#A36119") +
  geom_errorbar(aes(ymin = low, ymax = high), width = 0.08, linewidth = 0.65, colour = "#1C6070") +
  geom_point(size = 3.2, colour = "#1C6070") +
  annotate("text", x = 1, y = 0.265, label = "95% CI includes 0", size = 3.0, colour = "#8D3E3E") +
  annotate("text", x = 1, y = 0.235, label = "two-sided bootstrap p = 0.05099", size = 3.0, colour = "#8D3E3E") +
  scale_y_continuous(limits = c(-0.03, 0.29), breaks = c(0, 0.05, 0.1, 0.2), expand = expansion(mult = c(0.01, 0.02))) +
  labs(title = "Frozen contrast and gate boundary", subtitle = "Dashed line: prespecified threshold = 0.05", x = NULL, y = "Difference") +
  theme(plot.title = element_text(size = 9, face = "bold"), axis.text.x = element_text(size = 7))
gate_df <- data.frame(
  criterion = factor(c("Effect size", "95% CI lower bound", "Bootstrap p value"), levels = c("Effect size", "95% CI lower bound", "Bootstrap p value")),
  pass = c(g4$primary$G4_criteria$delta_at_least_0_05, g4$primary$G4_criteria$ci_lower_greater_than_0, g4$primary$G4_criteria$p_less_than_0_05),
  detail = c(
    sprintf("delta = %.4f (threshold >= 0.05)", g4$primary$observed_R2_TEST_minus_R3_NEW),
    sprintf("lower = %.5f (threshold > 0)", g4$primary$percentile_95_ci[[1]]),
    sprintf("p = %.5f (threshold < 0.05)", g4$primary$bootstrap_p_two_sided)
  )
)
gate_panel <- ggplot(gate_df, aes(criterion, 1, fill = pass)) +
  geom_tile(width = 0.84, height = 0.62, colour = "white") +
  geom_text(aes(label = ifelse(pass, "PASS", "FAIL")), y = 1, vjust = 0.15, fontface = "bold", size = 3.0) +
  geom_text(aes(label = detail), y = 0.53, size = 2.55, lineheight = 0.9, colour = "#25343B") +
  scale_fill_manual(values = c(`TRUE` = "#DCEFE8", `FALSE` = "#F1DADA"), guide = "none") +
  scale_y_continuous(limits = c(0.35, 1.35), breaks = NULL, expand = c(0, 0)) +
  labs(title = "Conjunctive G4 gate", subtitle = "All three conditions required; failure blocks a confirmed decline claim", x = NULL, y = NULL) +
  theme(plot.title = element_text(size = 9, face = "bold"), axis.text.x = element_text(size = 7.2), axis.ticks = element_blank())
fig2 <- p_left + p_right + gate_panel +
  plot_layout(design = "AB\nCC", heights = c(1, 0.9)) +
  plot_annotation(tag_levels = "a") &
  theme(plot.tag = element_text(size = 8, face = "bold"))
save_pub(fig2, "Figure_2_primary_endpoint_and_gate", width_mm = 183, height_mm = 118)

# Figure 3: frozen five-number summaries and means; no additional comparisons.
get_metric <- function(stratum, metric) {
  g4$strata[[stratum]][[metric]]
}
metric_map <- c(
  "Lesion-wise F1" = "lesion_f1",
  "Dice" = "dice",
  "Soft-map PR-AUC" = "pr_auc",
  "Absolute volume difference (mL)" = "abs_volume_difference_ml",
  "Absolute lesion-count difference" = "abs_lesion_count_difference"
)
metric_rows <- lapply(names(metric_map), function(label) {
  metric <- metric_map[[label]]
  do.call(rbind, lapply(strata, function(stratum) {
    s <- get_metric(stratum, metric)
    data.frame(stratum = stratum, metric = label, n = g4$strata[[stratum]]$fixed_n,
               mean = s$mean, median = s$median, q1 = s$q1, q3 = s$q3, min = s$min, max = s$max)
  }))
})
metric_df <- do.call(rbind, metric_rows)
metric_df$metric <- factor(metric_df$metric, levels = names(metric_map))
metric_df$stratum <- factor(metric_df$stratum, levels = strata)
metric_df$stratum_label <- factor(
  paste0(as.character(metric_df$stratum), "\n(n=", metric_df$n, ")"),
  levels = paste0(strata, "\n(n=", unname(counts[strata]), ")")
)
profile <- ggplot(metric_df, aes(stratum_label, mean, colour = stratum)) +
  geom_linerange(aes(ymin = min, ymax = max), linewidth = 0.55, colour = "#4B5559") +
  geom_linerange(aes(ymin = q1, ymax = q3), linewidth = 3.2) +
  geom_point(aes(shape = "Mean"), size = 2.25, colour = "#17242B") +
  geom_point(aes(y = median, shape = "Median"), size = 2.7, colour = "#17242B") +
  facet_wrap(~ metric, ncol = 3, scales = "free_y") +
  scale_colour_manual(values = c(R2_TEST = "#1C6070", SOOP = "#A36119", R3_NEW = "#8D3E3E"), guide = "none") +
  scale_shape_manual(values = c(Mean = 16, Median = 95), name = NULL) +
  scale_y_continuous(expand = expansion(mult = c(0.06, 0.16))) +
  labs(title = "Frozen case-level descriptive distributions", subtitle = "Labels show fixed n; whisker = range; thick segment = IQR; circle = mean; tick = median", x = NULL, y = "Metric value") +
  theme(plot.title = element_text(size = 9, face = "bold"), strip.text = element_text(size = 7.5, face = "bold"), legend.position = "top", legend.text = element_text(size = 7.5))
save_pub(profile, "Figure_3_descriptive_robustness_profile", width_mm = 183, height_mm = 126)

# Export editable source tables from the same frozen fields.
table1 <- data.frame(
  Stratum = strata,
  Role = unname(roles[strata]),
  Cases = unname(counts[strata]),
  Centers_or_sources = unname(centers[strata]),
  Inference_failure = "0%",
  Scoring_failure = "0%",
  Empty_prediction = sprintf("%.2f%%", 100 * c(g4$strata$R2_TEST$empty_prediction_rate, g4$strata$SOOP$empty_prediction_rate, g4$strata$R3_NEW$empty_prediction_rate)),
  Empty_ground_truth = sprintf("%.2f%%", 100 * c(g4$strata$R2_TEST$empty_ground_truth_rate, g4$strata$SOOP$empty_ground_truth_rate, g4$strata$R3_NEW$empty_ground_truth_rate))
)
write.csv(table1, file.path(table_dir, "Table_1_fixed_cohort_quality.csv"), row.names = FALSE, fileEncoding = "UTF-8")

table2 <- data.frame(
  Component = c("R2_TEST center-macro lesion-wise F1", "R3_NEW center-macro lesion-wise F1", "Difference", "Percentile 95% CI", "Two-sided bootstrap p", "Conjunctive G4 gate"),
  Frozen_result = c(sprintf("%.4f", g4$primary$R2_TEST$center_macro_lesion_f1), sprintf("%.4f", g4$primary$R3_NEW$center_macro_lesion_f1), sprintf("%.4f", g4$primary$observed_R2_TEST_minus_R3_NEW), sprintf("%.5f to %.5f", g4$primary$percentile_95_ci[[1]], g4$primary$percentile_95_ci[[2]]), sprintf("%.5f", g4$primary$bootstrap_p_two_sided), "Failed"),
  Criterion = c("-", "-", "at least 0.05", "lower bound above 0", "below 0.05", "all three conditions"),
  Pass = c("-", "-", "Yes", "No", "No", "No")
)
write.csv(table2, file.path(table_dir, "Table_2_primary_endpoint_gate.csv"), row.names = FALSE, fileEncoding = "UTF-8")

get_metric <- function(stratum, metric) {
  g4$strata[[stratum]][[metric]]
}
format_metric <- function(stratum, metric) {
  s <- get_metric(stratum, metric)
  sprintf("%.3f (%.3f); %.3f [%.3f-%.3f]; %.3f-%.3f", s$mean, s$sd, s$median, s$q1, s$q3, s$min, s$max)
}
table3 <- data.frame(
  Metric = c("Dice", "Lesion-wise F1", "Soft-map PR-AUC", "Absolute volume difference, mL", "Absolute lesion-count difference"),
  `R2_TEST (n=288)` = c(format_metric("R2_TEST", "dice"), format_metric("R2_TEST", "lesion_f1"), format_metric("R2_TEST", "pr_auc"), format_metric("R2_TEST", "abs_volume_difference_ml"), format_metric("R2_TEST", "abs_lesion_count_difference")),
  `SOOP (n=157)` = c(format_metric("SOOP", "dice"), format_metric("SOOP", "lesion_f1"), format_metric("SOOP", "pr_auc"), format_metric("SOOP", "abs_volume_difference_ml"), format_metric("SOOP", "abs_lesion_count_difference")),
  `R3_NEW (n=317)` = c(format_metric("R3_NEW", "dice"), format_metric("R3_NEW", "lesion_f1"), format_metric("R3_NEW", "pr_auc"), format_metric("R3_NEW", "abs_volume_difference_ml"), format_metric("R3_NEW", "abs_lesion_count_difference")),
  check.names = FALSE
)
write.csv(table3, file.path(table_dir, "Table_3_descriptive_metrics.csv"), row.names = FALSE, fileEncoding = "UTF-8")

writeLines(c(
  "Figure contract",
  "Core conclusion: the directional primary point estimate is not a confirmed meaningful decline because the frozen CI and p-value criteria failed.",
  "Evidence chain: Figure 1 links cohort composition, execution QC, and the frozen workflow; Figure 2 shows the primary estimate, uncertainty, and conjunctive gate status; Figure 3 shows the frozen five-number descriptive summaries for all prespecified secondary metrics.",
  "Archetypes: cohort/QC/workflow composite (Figure 1); primary estimate plus gate-status composite (Figure 2); quantitative distribution-summary grid (Figure 3).",
  "Backend: R, as saved by the project nature-figure preference.",
  "Export: SVG/PDF vector files plus 600-dpi TIFF and 300-dpi PNG; all files were generated from the frozen G4 summary JSON.",
  "Integrity note: no case-level rows, images, or new calculations were used by this script."
), file.path(out_dir, "docs", "figure_contract.md"))

message("G5 figures and editable CSV tables written to ", out_dir)
