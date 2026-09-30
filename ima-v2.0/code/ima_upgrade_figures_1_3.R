#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(ggplot2)
  library(patchwork)
  library(dplyr)
  library(svglite)
  library(ragg)
})

args <- commandArgs(trailingOnly = TRUE)
project_root <- if (length(args) >= 1) normalizePath(args[[1]], mustWork = TRUE) else getwd()
figure_root <- file.path(project_root, "投稿版_IMA_升级版_20260929", "02_图")
case_path <- file.path(project_root, "data", "authorized", "atlas_r3", "formal_v1.2", "upgrade_v2", "formal_case_characteristics.csv")
if (!file.exists(case_path)) stop("missing frozen case-characteristics source")

case_data <- read.csv(case_path, check.names = FALSE, stringsAsFactors = FALSE)
stratum_levels <- c("R2_TEST", "R3_NEW", "SOOP")
stratum_labels <- c(R2_TEST = "R2 test", R3_NEW = "R3 new-source", SOOP = "Single-source stress test")
stratum_palette <- c(R2_TEST = "#236A7A", R3_NEW = "#984447", SOOP = "#AD6718")
case_data <- case_data %>% mutate(stratum = factor(stratum, levels = stratum_levels))

theme_ima <- function(base_size = 7.6) {
  theme_classic(base_size = base_size, base_family = "Arial") +
    theme(
      axis.line = element_line(linewidth = 0.35, colour = "#252525"),
      axis.ticks = element_line(linewidth = 0.35, colour = "#252525"),
      axis.text = element_text(colour = "#252525"),
      strip.background = element_rect(fill = "#F1F3F4", colour = "#B7BCC0", linewidth = 0.3),
      strip.text = element_text(face = "bold"),
      plot.title = element_text(face = "bold", size = base_size + 0.6),
      plot.subtitle = element_text(colour = "#4A4A4A", size = base_size - 0.2),
      plot.tag = element_text(face = "bold", size = base_size + 1.2),
      plot.margin = margin(4, 5, 4, 5)
    )
}

save_figure <- function(plot, stem, width_mm = 183, height_mm = 125, dpi = 600) {
  width_in <- width_mm / 25.4
  height_in <- height_mm / 25.4
  svglite::svglite(paste0(stem, ".svg"), width = width_in, height = height_in, bg = "white")
  print(plot)
  dev.off()
  grDevices::cairo_pdf(paste0(stem, ".pdf"), width = width_in, height = height_in, family = "Arial", bg = "white")
  print(plot)
  dev.off()
  ragg::agg_tiff(paste0(stem, ".tiff"), width = width_in, height = height_in, units = "in", res = dpi, background = "white", compression = "lzw")
  print(plot)
  dev.off()
  ragg::agg_png(paste0(stem, ".png"), width = width_in, height = height_in, units = "in", res = 300, background = "white")
  print(plot)
  dev.off()
  outputs <- paste0(stem, c(".svg", ".pdf", ".tiff", ".png"))
  if (!all(file.exists(outputs)) || any(file.info(outputs)$size <= 0)) stop("figure export failed")
}

cohort <- case_data %>% count(stratum, name = "n")
p1a <- ggplot(cohort, aes(x = n, y = stratum, fill = stratum)) +
  geom_col(width = 0.58, colour = "#333333", linewidth = 0.35) +
  geom_text(aes(label = paste0("n = ", n)), hjust = 1.08, colour = "white", fontface = "bold", size = 2.8) +
  scale_fill_manual(values = stratum_palette, guide = "none") +
  scale_y_discrete(labels = stratum_labels) +
  scale_x_continuous(limits = c(0, 345), breaks = c(0, 100, 200, 300), expand = c(0, 0)) +
  labs(x = "Formal cases", y = NULL, title = "Fixed 762-case cohort", subtitle = "Pilot-36 excluded before formal evaluation") +
  theme_ima()

flow <- ggplot() +
  annotate("rect", xmin = 0.08, xmax = 0.92, ymin = 0.73, ymax = 0.94, fill = "#E8F0F2", colour = "#236A7A", linewidth = 0.5) +
  annotate("text", x = 0.50, y = 0.86, label = "Training-resource audit", fontface = "bold", size = 3.0) +
  annotate("text", x = 0.50, y = 0.78, label = "ATLAS R2: 655 cases  |  formal overlap: 0", size = 2.45, colour = "#3F4A4D") +
  annotate("rect", xmin = 0.08, xmax = 0.47, ymin = 0.41, ymax = 0.64, fill = "#F5F5F5", colour = "#555555", linewidth = 0.5) +
  annotate("text", x = 0.275, y = 0.55, label = "Default nnU-Net", fontface = "bold", size = 2.85) +
  annotate("text", x = 0.275, y = 0.47, label = "five-fold ensemble", size = 2.4) +
  annotate("rect", xmin = 0.53, xmax = 0.92, ymin = 0.41, ymax = 0.64, fill = "#E9F4EC", colour = "#238B45", linewidth = 0.5) +
  annotate("text", x = 0.725, y = 0.55, label = "SynthStroke (2025)", fontface = "bold", size = 2.55) +
  annotate("text", x = 0.725, y = 0.47, label = "synthetic + real training", size = 2.25) +
  annotate("rect", xmin = 0.17, xmax = 0.83, ymin = 0.08, ymax = 0.31, fill = "#F7ECEC", colour = "#984447", linewidth = 0.5) +
  annotate("text", x = 0.50, y = 0.22, label = "Same fixed 762-case test set", fontface = "bold", size = 2.95) +
  annotate("text", x = 0.50, y = 0.14, label = "paired centers  |  fixed metrics  |  uncertainty audit", size = 2.05) +
  annotate("segment", x = 0.50, xend = 0.275, y = 0.73, yend = 0.65, arrow = arrow(length = unit(2.0, "mm")), linewidth = 0.42) +
  annotate("segment", x = 0.50, xend = 0.725, y = 0.73, yend = 0.65, arrow = arrow(length = unit(2.0, "mm")), linewidth = 0.42) +
  annotate("segment", x = 0.275, xend = 0.42, y = 0.40, yend = 0.32, arrow = arrow(length = unit(2.0, "mm")), linewidth = 0.42) +
  annotate("segment", x = 0.725, xend = 0.58, y = 0.40, yend = 0.32, arrow = arrow(length = unit(2.0, "mm")), linewidth = 0.42) +
  coord_cartesian(xlim = c(0, 1), ylim = c(0, 1), clip = "off") +
  labs(title = "Outcome-blinded model comparison", subtitle = "Immutable checkpoints; no threshold tuning or post-processing") +
  theme_void(base_family = "Arial", base_size = 8) +
  theme(plot.title = element_text(face = "bold", size = 8.2), plot.subtitle = element_text(size = 7.1, colour = "#4A4A4A"), plot.margin = margin(4, 5, 4, 5))

audit <- data.frame(
  item = factor(c("Training-formal overlap", "Pilot-formal overlap", "Formal cases scored", "Shared R2/R3 center labels"), levels = rev(c("Training-formal overlap", "Pilot-formal overlap", "Formal cases scored", "Shared R2/R3 center labels"))),
  value = c("0 cases", "0 cases", "762 / 762", "4 labels"),
  class = c("pass", "pass", "pass", "boundary")
)
p1c <- ggplot(audit, aes(x = 1, y = item)) +
  geom_tile(aes(fill = class), width = 0.95, height = 0.72, colour = "white", linewidth = 0.8) +
  geom_text(aes(label = value), fontface = "bold", size = 3.0, colour = "#242424") +
  scale_fill_manual(values = c(pass = "#DCEFE7", boundary = "#F3DFC5"), guide = "none") +
  scale_x_continuous(limits = c(0.5, 1.5), expand = c(0, 0)) +
  labs(x = NULL, y = NULL, title = "Independence and completion audit", subtitle = "Record non-overlap does not prove subject independence") +
  theme_ima() +
  theme(axis.line = element_blank(), axis.ticks = element_blank(), axis.text.x = element_blank(), panel.grid = element_blank())

figure1 <- (p1a | flow) / p1c + plot_layout(heights = c(1.2, 0.82), widths = c(0.86, 1.25)) + plot_annotation(tag_levels = "a")
save_figure(figure1, file.path(figure_root, "Figure_1_study_design_and_quality"), height_mm = 126)

positive_volume <- case_data %>% filter(gt_volume_ml > 0)
p3a <- ggplot(positive_volume, aes(x = stratum, y = gt_volume_ml, fill = stratum)) +
  geom_violin(scale = "width", trim = TRUE, alpha = 0.62, colour = NA) +
  geom_boxplot(width = 0.18, outlier.shape = NA, fill = "white", colour = "#333333", linewidth = 0.42) +
  scale_fill_manual(values = stratum_palette, guide = "none") +
  scale_x_discrete(labels = stratum_labels) +
  scale_y_log10(breaks = c(0.01, 0.1, 1, 10, 100), labels = c("0.01", "0.1", "1", "10", "100")) +
  labs(x = NULL, y = "Ground-truth lesion volume (mL, log scale)", title = "Lesion burden") +
  theme_ima() + theme(axis.text.x = element_text(angle = 18, hjust = 1))

p3b <- ggplot(case_data, aes(x = stratum, y = gt_lesion_count, fill = stratum)) +
  geom_violin(scale = "width", trim = TRUE, alpha = 0.62, colour = NA) +
  geom_boxplot(width = 0.18, outlier.shape = NA, fill = "white", colour = "#333333", linewidth = 0.42) +
  scale_fill_manual(values = stratum_palette, guide = "none") +
  scale_x_discrete(labels = stratum_labels) +
  scale_y_sqrt(breaks = c(0, 1, 4, 9, 16, 25, 49, 81)) +
  labs(x = NULL, y = "Ground-truth lesion count (square-root scale)", title = "Lesion multiplicity") +
  theme_ima() + theme(axis.text.x = element_text(angle = 18, hjust = 1))

center_data <- case_data %>% count(stratum, center, name = "cases") %>% group_by(stratum) %>% arrange(cases, .by_group = TRUE) %>% mutate(rank = row_number()) %>% ungroup()
p3c <- ggplot(center_data, aes(x = rank, y = cases, colour = stratum)) +
  geom_segment(aes(xend = rank, y = 0.8, yend = cases), linewidth = 0.42, alpha = 0.72) +
  geom_point(size = 1.9) +
  facet_wrap(~stratum, scales = "free_x", labeller = as_labeller(stratum_labels), nrow = 1) +
  scale_colour_manual(values = stratum_palette, guide = "none") +
  scale_y_log10(breaks = c(1, 2, 5, 10, 20, 50, 100, 200)) +
  labs(x = "Centers or source, ordered by sample size", y = "Cases per center/source (log scale)", title = "Unequal source-cluster sizes", subtitle = "Center-macro estimates give equal weight to each center") +
  theme_ima() + theme(axis.text.x = element_blank(), axis.ticks.x = element_blank())

figure3 <- (p3a | p3b) / p3c + plot_layout(heights = c(1.08, 0.88)) + plot_annotation(tag_levels = "a")
save_figure(figure3, file.path(figure_root, "Figure_3_descriptive_robustness_profile"), height_mm = 139)

public_case_source <- case_data %>%
  arrange(stratum, gt_volume_ml, gt_lesion_count) %>%
  group_by(stratum) %>%
  mutate(display_index = row_number()) %>%
  ungroup() %>%
  transmute(
    display_index,
    stratum = as.character(stratum),
    gt_volume_ml,
    gt_lesion_count,
    gt_empty
  )
public_center_source <- center_data %>%
  transmute(
    stratum = as.character(stratum),
    center_rank = rank,
    cases
  )
write.csv(cohort %>% mutate(stratum = as.character(stratum)), file.path(figure_root, "Figure_1_cohort_source_data.csv"), row.names = FALSE, quote = TRUE)
write.csv(public_case_source, file.path(figure_root, "Figure_3_case_source_data.csv"), row.names = FALSE, quote = TRUE)
write.csv(public_center_source, file.path(figure_root, "Figure_3_center_size_source_data.csv"), row.names = FALSE, quote = TRUE)

receipt <- data.frame(
  figure = c("Figure 1", "Figure 3"),
  conclusion = c("The two-model evaluation used a fixed cohort with audited record-level training-evaluation separation.", "The source strata differ in lesion burden, multiplicity, and cluster size, motivating source- and center-aware analysis."),
  primary_panel = c("b", "c"),
  claim_boundary = c("Same public release family; subject-level or prospective independence is not established.", "Descriptive cohort structure only; no causal attribution to source."),
  stringsAsFactors = FALSE
)
write.csv(receipt, file.path(figure_root, "Figures_1_3_contract_and_render_receipt.csv"), row.names = FALSE, quote = TRUE)
cat("Figure 1 and Figure 3 exported from R.\n")
