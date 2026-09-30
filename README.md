# Stroke lesion segmentation robustness archive v2.0

Reproducibility archive for the manuscript *Source robustness and predictive uncertainty of two stroke lesion segmentation models: a 762-case public benchmark*.

## Study boundary

The formal cohort contains 762 publicly released, de-identified T1-weighted MRI cases: 288 in `R2_TEST`, 157 in `SOOP`, and 317 in `R3_NEW`. The original v1.2 analysis and its inconclusive prespecified decision are preserved. Version 2.0 adds a complete same-case comparison between the five-fold reference nnU-Net pipeline and the 2025 SynthStroke checkpoint, together with probability calibration, uncertainty-error association, risk-coverage analysis, and six performance-blinded qualitative examples.

The comparison evaluates complete model pipelines. It does not isolate architecture, establish causal source effects, provide independent prospective clinical validation, or support deployment-readiness claims.

## Version 2.0 contents

The `ima-v2.0/` directory contains the public submission supplement:

- Tables S1-S8 covering metric definitions, reproducibility, retained anomalies, training-evaluation separation, cohort structure, paired model comparison, uncertainty, and comparator eligibility.
- Frozen protocols and amendments, including the outcome-blinded comparator-feasibility decision.
- Aggregate results and source data for Figures 1 and 3-6.
- R and Python scripts used for inference provenance, comparative scoring, source-data extraction, and figure rendering.
- Public completion, model-version, source-audit, and rendering receipts.
- A SHA-256 manifest for all included files.

The original v1.2 scripts, protocols, figures, and tables remain at the repository root for version-history continuity.

## Main findings represented in the archive

Both active model pipelines completed all 762 cases. In the new-source multicenter stratum, the paired SynthStroke-minus-reference center-macro lesion-wise F1 difference was -0.151 (95% CI -0.241 to -0.076). In the reference multicenter stratum, it was -0.232 (-0.274 to -0.191). Model-specific `R2_TEST - R3_NEW` gaps were 0.123 for the reference model and 0.042 for SynthStroke. These extension analyses are exploratory and do not alter the original prespecified conclusion.

## Reproduction scope

The repository provides the exact public aggregate inputs needed to regenerate the reported tables and Figures 1 and 3-6. Full inference requires separate lawful access to the source imaging data, released reference masks, model weights, and the restricted local token-to-file mapping. Those inputs are not redistributed here.

## Data access and privacy

The source imaging data are available through the ISLES 2026 release page and the ATLAS resource, subject to their original access and reuse terms:

- https://isles-26.grand-challenge.org/dataset/
- https://doi.org/10.1038/s41597-022-01401-7

This repository does not contain patient-level images, masks, predictions, probability arrays, complete case-level metric files, source filenames, worker assignments, or subject-to-center linkage records. Six pseudonymous qualitative-case selection/display records are included only to audit the performance-blinded sampling procedure. Center labels in public source data are replaced by within-stratum indices, and uncertainty-error display data are reduced to plotted decile summaries.

## Authors

- Mengyao Jiang, Department of Basic Medical Sciences, Hebei Medical University. ORCID: https://orcid.org/0009-0003-6210-5270
- Zimo Zhao, Department of Basic Medical Sciences, Hebei Medical University.

Correspondence: Mengyao Jiang, 24011280031@stu.hebmu.edu.cn.

## Citation and persistent identifier

The version-independent Zenodo concept DOI is https://doi.org/10.5281/zenodo.22868191. Cite the version-specific DOI shown on the Zenodo landing page when referring to an exact release. The GitHub `v2.0.0` release is an immutable code-release URL for this archive.

## Licence

The authors' code and documentation in this archive are released under the MIT License. The source imaging data, released masks, external model weights, and third-party software remain subject to their original terms and are not relicensed or redistributed here.
