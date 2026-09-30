#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(ggplot2)
  library(patchwork)
  library(dplyr)
  library(tidyr)
  library(svglite)
  library(ragg)
})

args <- commandArgs(trailingOnly = TRUE)
project_root <- if (length(args) >= 1) normalizePath(args[[1]], mustWork = TRUE) else getwd()
figure_root <- file.path(project_root, "投稿版_IMA_升级版_20260929", "02_图")

model_levels <- c("Default nnU-Net", "SynthStroke (2025)")
stratum_levels <- c("R2_TEST", "R3_NEW", "SOOP")
model_palette <- c(
  "Default nnU-Net" = "#2B2B2B",
  "SynthStroke (2025)" = "#238B45"
)
stratum_labels <- c(
  "R2_TEST" = "R2 test",
  "R3_NEW" = "R3 new-source",
  "SOOP" = "Single-source stress test",
  "ALL" = "All cases"
)

theme_ima <- function(base_size = 7.2) {
  theme_classic(base_size = base_size, base_family = "Arial") +
    theme(
      axis.line = element_line(linewidth = 0.35, colour = "black"),
      axis.ticks = element_line(linewidth = 0.35, colour = "black"),
      axis.title = element_text(size = base_size),
      axis.text = element_text(size = base_size - 0.4),
      legend.title = element_text(size = base_size - 0.2),
      legend.text = element_text(size = base_size - 0.5),
      strip.text = element_text(size = base_size - 0.1, face = "bold"),
      strip.background = element_rect(fill = "#F3F3F3", colour = "#BDBDBD", linewidth = 0.3),
      panel.spacing = grid::unit(3, "mm"),
      plot.title = element_text(size = base_size + 0.4, face = "bold"),
      plot.tag = element_text(size = base_size + 1.2, face = "bold"),
      plot.margin = margin(4, 5, 4, 5),
      legend.key.height = grid::unit(3.5, "mm")
    )
}

save_figure <- function(plot, stem, width_mm = 183, height_mm = 140, dpi = 600) {
  width_in <- width_mm / 25.4
  height_in <- height_mm / 25.4
  svg_path <- paste0(stem, ".svg")
  pdf_path <- paste0(stem, ".pdf")
  tiff_path <- paste0(stem, ".tiff")
  png_path <- paste0(stem, ".png")

  svglite::svglite(svg_path, width = width_in, height = height_in, bg = "white")
  print(plot)
  dev.off()
  grDevices::pdf(pdf_path, width = width_in, height = height_in, family = "Helvetica", bg = "white")
  print(plot)
  dev.off()
  ragg::agg_tiff(tiff_path, width = width_in, height = height_in, units = "in", res = dpi, background = "white", compression = "lzw")
  print(plot)
  dev.off()
  ragg::agg_png(png_path, width = width_in, height = height_in, units = "in", res = 300, background = "white")
  print(plot)
  dev.off()

  files <- c(svg_path, pdf_path, tiff_path, png_path)
  if (!all(file.exists(files)) || any(file.info(files)$size <= 0)) stop("figure export failed")
  invisible(files)
}

read_required <- function(name) {
  path <- file.path(figure_root, name)
  if (!file.exists(path)) stop(paste("missing source data:", path))
  read.csv(path, check.names = FALSE, stringsAsFactors = FALSE)
}

center_data <- read_required("Figure_5_source_data.csv") %>%
  mutate(
    model = factor(model, levels = model_levels),
    stratum = factor(stratum, levels = stratum_levels)
  )
summary_data <- read_required("Figure_5_summary_source_data.csv") %>%
  mutate(
    model = factor(model, levels = model_levels),
    stratum = factor(stratum, levels = stratum_levels)
  )
comparison_data <- read_required("Figure_5_pairwise_source_data.csv") %>%
  mutate(
    comparator_label = factor(comparator_label, levels = rev(model_levels[-1])),
    stratum = factor(stratum, levels = c("R3_NEW", "R2_TEST")),
    significance = "exploratory"
  )
gap_data <- read_required("Figure_5_gap_source_data.csv") %>%
  mutate(model_label = factor(model_label, levels = rev(model_levels)))

p5a <- ggplot(center_data, aes(x = stratum, y = lesion_f1, colour = model)) +
  geom_point(position = position_jitterdodge(jitter.width = 0.11, dodge.width = 0.66), alpha = 0.48, size = 1.05) +
  geom_errorbar(
    data = summary_data,
    aes(x = stratum, ymin = ci_lower, ymax = ci_upper, colour = model, group = model),
    inherit.aes = FALSE,
    position = position_dodge(width = 0.66), width = 0.12, linewidth = 0.48
  ) +
  geom_point(
    data = summary_data,
    aes(x = stratum, y = center_macro_lesion_f1, colour = model, group = model),
    inherit.aes = FALSE,
    position = position_dodge(width = 0.66), shape = 21, fill = "white", stroke = 0.65, size = 2.2
  ) +
  scale_colour_manual(values = model_palette) +
  scale_x_discrete(labels = stratum_labels) +
  scale_y_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.2), expand = expansion(mult = c(0, 0.03))) +
  labs(x = NULL, y = "Center-macro lesion-wise F1", colour = NULL, title = "Same-cohort performance") +
  theme_ima() +
  theme(axis.text.x = element_text(angle = 18, hjust = 1), legend.position = "top")

p5b <- ggplot(comparison_data, aes(x = estimate, y = comparator_label, colour = comparator_label)) +
  geom_vline(xintercept = 0, linewidth = 0.4, colour = "#777777") +
  geom_errorbarh(aes(xmin = ci_lower, xmax = ci_upper), height = 0.16, linewidth = 0.55) +
  geom_point(shape = 21, fill = "white", stroke = 0.7, size = 2.3) +
  geom_text(aes(label = significance), x = Inf, hjust = 1.04, colour = "#303030", size = 2.2) +
  facet_wrap(~stratum, labeller = as_labeller(stratum_labels), ncol = 1) +
  scale_colour_manual(values = model_palette, guide = "none") +
  scale_x_continuous(expand = expansion(mult = c(0.08, 0.35))) +
  labs(x = "Comparator minus default lesion-wise F1", y = NULL, title = "Paired center differences") +
  theme_ima()

p5c <- ggplot(gap_data, aes(x = estimate, y = model_label, colour = model_label)) +
  geom_vline(xintercept = 0, linewidth = 0.4, colour = "#777777") +
  geom_errorbarh(aes(xmin = ci_lower, xmax = ci_upper), height = 0.17, linewidth = 0.55) +
  geom_point(shape = 21, fill = "white", stroke = 0.7, size = 2.3) +
  scale_colour_manual(values = model_palette, guide = "none") +
  labs(x = "R2 test minus R3 new-source lesion-wise F1", y = NULL, title = "Source-stratum gap") +
  theme_ima()

figure5 <- p5a + (p5b / p5c) +
  plot_layout(widths = c(1.62, 1), guides = "collect") +
  plot_annotation(tag_levels = "a") &
  theme(legend.position = "top")
save_figure(figure5, file.path(figure_root, "Figure_5_multimodel_source_robustness"), height_mm = 132)

risk_data <- read_required("Figure_6_risk_coverage_source_data.csv") %>%
  mutate(
    model_label = factor(model_label, levels = model_levels),
    stratum = factor(stratum, levels = c("ALL", stratum_levels)),
    coverage_percent = 100 * coverage
  )
reliability_data <- read_required("Figure_6_reliability_source_data.csv") %>%
  filter(stratum == "R3_NEW", voxel_n > 0) %>%
  mutate(model_label = factor(model_label, levels = model_levels))
uncertainty_data <- read_required("Figure_6_uncertainty_error_source_data.csv") %>%
  filter(stratum == "R3_NEW") %>%
  mutate(model = factor(model, levels = model_levels)) %>%
  group_by(model) %>%
  mutate(uncertainty_decile = ntile(case_uncertainty, 10)) %>%
  group_by(model, uncertainty_decile) %>%
  summarise(
    uncertainty = mean(case_uncertainty),
    error = mean(one_minus_dice),
    se = sd(one_minus_dice) / sqrt(n()),
    n = n(),
    .groups = "drop"
  )

p6a <- ggplot(risk_data, aes(x = coverage_percent, y = mean_error, colour = model_label, group = model_label)) +
  geom_line(linewidth = 0.62) +
  geom_point(size = 1.35) +
  facet_wrap(~stratum, labeller = as_labeller(stratum_labels), nrow = 1) +
  scale_colour_manual(values = model_palette) +
  scale_x_reverse(breaks = c(100, 80, 60, 50)) +
  scale_y_continuous(limits = c(0, NA), expand = expansion(mult = c(0, 0.06))) +
  labs(x = "Retained cases with lowest uncertainty (%)", y = "Mean Dice error (1 - Dice)", colour = NULL, title = "Risk-coverage profile") +
  theme_ima() +
  theme(legend.position = "top")

p6b <- ggplot(reliability_data, aes(x = mean_predicted_probability, y = observed_frequency, colour = model_label, size = voxel_n)) +
  geom_abline(slope = 1, intercept = 0, linewidth = 0.45, linetype = "dashed", colour = "#777777") +
  geom_line(aes(group = model_label), linewidth = 0.55) +
  geom_point(alpha = 0.85) +
  scale_colour_manual(values = model_palette) +
  scale_size_continuous(trans = "log10", range = c(1.2, 3.6), guide = "none") +
  coord_equal(xlim = c(0, 1), ylim = c(0, 1), expand = FALSE) +
  labs(x = "Mean predicted probability", y = "Observed lesion frequency", colour = NULL, title = "R3 reliability") +
  theme_ima() +
  theme(legend.position = "none")

p6c <- ggplot(uncertainty_data, aes(x = uncertainty, y = error, colour = model, group = model)) +
  geom_errorbar(aes(ymin = pmax(0, error - 1.96 * se), ymax = pmin(1, error + 1.96 * se)), width = 0, linewidth = 0.45, alpha = 0.7) +
  geom_line(linewidth = 0.58) +
  geom_point(size = 1.55) +
  scale_colour_manual(values = model_palette) +
  scale_y_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.2)) +
  labs(x = "Mean predictive entropy (decile means)", y = "Mean Dice error (1 - Dice)", colour = NULL, title = "R3 uncertainty-error association") +
  theme_ima() +
  theme(legend.position = "none")

figure6 <- p6a / (p6b | p6c) +
  plot_layout(heights = c(1.05, 1)) +
  plot_annotation(tag_levels = "a")
save_figure(figure6, file.path(figure_root, "Figure_6_predictive_uncertainty"), height_mm = 145)

receipt <- data.frame(
  figure = c("Figure 5", "Figure 6"),
  conclusion = c(
    "Model choice may alter same-cohort source-stratified performance and source-gap estimates.",
    "Predictive uncertainty is evaluated as retrospective quality-control evidence through calibration, association, and risk coverage."
  ),
  primary_panel = c("a", "a"),
  claim_boundary = c(
    "Same public release family; no prospective external validation or causal source attribution.",
    "No clinical calibration or deployment-safety claim."
  ),
  stringsAsFactors = FALSE
)
write.csv(receipt, file.path(figure_root, "Figures_5_6_contract_and_render_receipt.csv"), row.names = FALSE, quote = TRUE)
cat("Figure 5 and Figure 6 exported from R.\n")
