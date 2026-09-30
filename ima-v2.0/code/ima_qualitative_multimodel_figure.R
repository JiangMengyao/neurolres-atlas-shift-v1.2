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
restricted_path <- file.path(project_root, "data", "authorized", "atlas_r3", "formal_v1.2", "upgrade_v2", "Figure_4_multimodel_restricted_pixels.csv")
figure_root <- file.path(project_root, "投稿版_IMA_升级版_20260929", "02_图")
metadata_path <- file.path(figure_root, "Figure_4_multimodel_panel_metadata.csv")

if (!file.exists(restricted_path) || !file.exists(metadata_path)) stop("qualitative source data are incomplete")
pixels <- read.csv(restricted_path, stringsAsFactors = FALSE)
metadata <- read.csv(metadata_path, stringsAsFactors = FALSE)

model_labels <- c(
  ground_truth = "Ground truth",
  default = "Default nnU-Net",
  synthstroke = "SynthStroke (2025)"
)
model_colours <- c(
  "Ground truth" = "#00D5E8",
  "Default nnU-Net" = "#E6007E",
  "SynthStroke (2025)" = "#35A853"
)
model_linetypes <- c(
  "Ground truth" = "solid",
  "Default nnU-Net" = "solid",
  "SynthStroke (2025)" = "longdash"
)
stratum_labels <- c(R2_TEST = "R2 test", R3_NEW = "R3 new-source", SOOP = "Single-source stress test")

long_masks <- pixels %>%
  select(case_label, x, y, all_of(names(model_labels))) %>%
  pivot_longer(cols = all_of(names(model_labels)), names_to = "model_key", values_to = "mask") %>%
  mutate(model = factor(unname(model_labels[model_key]), levels = unname(model_labels)))

make_panel <- function(label) {
  image_data <- pixels %>% filter(case_label == label)
  contour_data <- long_masks %>% filter(case_label == label)
  info <- metadata %>% filter(case_label == label)
  title <- paste0(
    label, "  ", stratum_labels[[info$stratum]], " | ",
    ifelse(info$lesion_band == "small", "small lesion", "large lesion"),
    " | GT ", formatC(info$gt_volume_ml, format = "f", digits = 2), " mL"
  )
  y_max <- max(image_data$y)
  x_end <- min(max(image_data$x) - 4, 5 + 20 / info$horizontal_pixel_size_mm)
  ggplot(image_data, aes(x = x, y = y)) +
    geom_raster(aes(fill = intensity), interpolate = FALSE) +
    geom_contour(
      data = contour_data,
      aes(z = mask, colour = model, linetype = model, group = model),
      breaks = 0.5, linewidth = 0.48, show.legend = TRUE
    ) +
    annotate("segment", x = 5, xend = x_end, y = y_max - 5, yend = y_max - 5, colour = "white", linewidth = 0.8) +
    annotate("text", x = 5, y = y_max - 8, label = "20 mm", colour = "white", size = 2.2, hjust = 0, vjust = 1) +
    scale_fill_gradient(low = "black", high = "white", limits = c(0, 1), guide = "none") +
    scale_colour_manual(values = model_colours, drop = FALSE) +
    scale_linetype_manual(values = model_linetypes, drop = FALSE) +
    scale_y_reverse(expand = c(0, 0)) +
    scale_x_continuous(expand = c(0, 0)) +
    coord_fixed(clip = "on") +
    labs(title = title, colour = NULL, linetype = NULL) +
    theme_void(base_family = "Arial", base_size = 7) +
    theme(
      plot.title = element_text(size = 6.6, face = "bold", colour = "#202020", margin = margin(b = 2)),
      plot.margin = margin(2, 2, 2, 2),
      panel.border = element_rect(colour = "#A8A8A8", fill = NA, linewidth = 0.35),
      legend.position = "bottom",
      legend.text = element_text(size = 6),
      legend.key.width = grid::unit(7, "mm")
    )
}

panels <- lapply(letters[1:6], make_panel)
figure <- wrap_plots(panels, ncol = 3, guides = "collect") &
  theme(legend.position = "bottom")

stem <- file.path(figure_root, "Figure_4_performance_blinded_qualitative_cases")
width <- 183 / 25.4
height <- 132 / 25.4
svglite::svglite(paste0(stem, ".svg"), width = width, height = height, bg = "white")
print(figure)
dev.off()
grDevices::pdf(paste0(stem, ".pdf"), width = width, height = height, family = "Helvetica", bg = "white")
print(figure)
dev.off()
ragg::agg_tiff(paste0(stem, ".tiff"), width = width, height = height, units = "in", res = 600, compression = "lzw", background = "white")
print(figure)
dev.off()
ragg::agg_png(paste0(stem, ".png"), width = width, height = height, units = "in", res = 300, background = "white")
print(figure)
dev.off()

outputs <- paste0(stem, c(".svg", ".pdf", ".tiff", ".png"))
if (!all(file.exists(outputs)) || any(file.info(outputs)$size <= 0)) stop("qualitative export failed")
cat("Figure 4 exported from R.\n")
