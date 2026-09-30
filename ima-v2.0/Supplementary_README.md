# Supplementary materials S1-S8

The supplementary package documents the frozen analysis contract, training-evaluation independence, contemporary comparator selection, complete execution, and the source data required to reproduce aggregate tables and figures.

Tables S1-S8 cover metric definitions; software, model, and hash receipts; retained header anomalies; training/pilot/formal overlap; cohort structure; paired model comparison; calibration and uncertainty; and comparator eligibility. The included protocol amendments record the outcome-blinded feasibility decision that excluded prohibitively slow candidates before any comparator ground-truth scoring.

The immutable E2 protocol used the phrase "out-of-family comparator" to distinguish SynthStroke from the reference nnU-Net method family. It does not mean an external dataset or independent clinical-validation cohort; both evaluated pipelines were tested within the same public release family. Current manuscript and table wording uses "methodologically distinct contemporary comparator" to avoid that ambiguity while preserving the original protocol file and hash.

Figure 4 cases were selected within source and lesion-burden cells using fixed SHA-256 ordering before model metrics or image appearance were accessed. Figures 1 and 3-6 were rendered from the supplied source data with R. Figure 2 preserves the original frozen primary analysis.

Only aggregate or non-identifying material is included. The six qualitative panels retain pseudonymous selection/display records to make the performance-blinded sampling auditable. Center labels are replaced by within-stratum indices and the uncertainty-error display source is reduced to decile summaries. Patient-level images, masks, predictions, probability maps, full-cohort case metrics, source filenames, worker assignments, and linkage records are excluded.
