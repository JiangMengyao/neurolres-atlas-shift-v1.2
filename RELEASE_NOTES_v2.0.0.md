# Version 2.0.0

This release upgrades the original single-model archive to the complete two-model analysis prepared for the International Journal of Imaging Systems and Technology.

## Added

- Complete 762-case same-cohort evaluation of the reference nnU-Net pipeline and SynthStroke.
- Center-aware paired model comparisons and model-specific source-stratum gaps.
- Whole-brain and balanced Brier scores, reliability curves, entropy-error associations, and risk-coverage profiles.
- Six performance-blinded qualitative cases selected by lesion burden and a fixed hash before comparative performance access.
- Tables S1-S8, aggregate figure source data, frozen protocol amendments, execution receipts, and a SHA-256 manifest.

## Preserved

- The original fixed cohort, estimand, bootstrap, and inconclusive decision rule.
- The immutable v1.2 record and its version-specific DOI.
- Explicit boundaries against architecture causation, independent clinical validation, and deployment-readiness claims.

## Privacy boundary

No patient-level images, masks, predictions, probability arrays, complete case-level metrics, source filenames, worker assignments, or subject-to-center linkage records are included. Six pseudonymous qualitative-case selection/display records are provided only for auditability.
