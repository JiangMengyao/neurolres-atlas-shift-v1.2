# NEUROLRES-ATLAS-SHIFT v1.2

Reproducibility archive for a frozen external evaluation of a five-fold stroke-lesion segmentation ensemble under a protocol-defined source/temporal shift.

## Study boundary

This repository supports the manuscript titled *Evaluating a resource-efficient five-fold stroke-lesion segmentation ensemble under a protocol-defined source/temporal shift: multicenter external evaluation with a single-source stress test*.

The formal cohort contained 762 cases: 288 in `R2_TEST`, 157 in `SOOP`, and 317 in `R3_NEW`. All cases completed inference and scoring. The prespecified G4 gate failed because the 95% confidence interval included zero and the two-sided bootstrap p value did not meet the frozen threshold. This archive does not support claims of confirmed degradation, equivalence, non-inferiority, clinical benefit, clinical readiness, or proven robustness.

## Repository contents

- `scripts/neurolres_atlas_shift_v1_2_g4_formal_score_r2.py`: exact formal Resume-2 scorer used for G4; SHA-256 `0fe6631bcd50aabe1289422e3913ed31c0ebff96cd2a5b9c2cb85308e35c1732`.
- `scripts/neurolres_atlas_shift_v1_2_g3_completeness.py`: frozen output-triplet completeness checker.
- `scripts/neurolres_atlas_shift_v1_2_g5_figures.R`: deterministic figure and table regeneration from the public aggregate summary.
- `data/frozen_g4_summary_public.json`: non-identifying aggregate G4 result fields used by the figure script.
- `protocols/`: frozen protocol, non-identifying G3/G5 locks, and E1/E2 implementation errata. The G4 Resume-2 lock is represented by its immutable receipt hash rather than its internal worker record.
- `docs/`: metric definitions, software and execution receipt, header-anomaly disclosure, and metadata-independence audit.
- `tables/` and `figures/`: editable source tables and manuscript figure exports generated from the frozen summary.

## Reproduce the figures and tables

R 4.5.1 was used with `jsonlite` 2.0.0, `ggplot2` 4.0.3, `patchwork` 1.3.2, `ragg` 1.5.2, and `svglite` 2.2.2.

```bash
Rscript scripts/neurolres_atlas_shift_v1_2_g5_figures.R
```

The script reads only `data/frozen_g4_summary_public.json`. It does not access case-level records or recompute inferential statistics.

## Official scoring provenance

The analysis used the official ISLES'26 scorer repository at commit `e589d022953f797bdc6acc1ce9701f793dab295a`. The exact `utils/eval_utils.py` file had SHA-256 `73668f48b70a56fe1ce785701595627ac3a6086412fb0f85b211ff7dc09ffcfd`. Panoptica was pinned to commit `3cc264a470b5c02853aace0f30d6a9af21335abd`.

The Python scoring environment was Python 3.12.5 with NumPy 2.2.6, scikit-learn 1.6.1, SciPy 1.18.1, Panoptica 2.1.7, connected-components-3d 3.29.0, and NiBabel 5.3.3. See `docs/Table_S2_reproducibility_receipt.csv` for the complete receipt.

## Data access and privacy

The source imaging data are available through the ISLES'26 release page and the ATLAS resource, subject to their applicable access and reuse terms:

- https://isles-26.grand-challenge.org/dataset/
- https://doi.org/10.1038/s41597-022-01401-7

This repository contains no patient-level images, masks, predictions, probability arrays, case-level metric files, restricted token mappings, filenames, worker indices, or subject/center linkage records. The five retained header anomalies are disclosed only in aggregate in `docs/Table_S3_header_anomaly_disclosure.csv`.

## Authors

- Mengyao Jiang, Department of Basic Medical Sciences, Hebei Medical University. ORCID: https://orcid.org/0009-0003-6210-5270
- Zimo Zhao, Department of Basic Medical Sciences, Hebei Medical University.

Correspondence: Mengyao Jiang, 24011280031@stu.hebmu.edu.cn.

## Citation

Use the metadata in `CITATION.cff`. The v1.2.0 GitHub release is archived in Zenodo at https://doi.org/10.5281/zenodo.22868192. The DOI identifies the exact release archive and is linked to the repository and `v1.2.0` release.

## Licence

This code archive is released under the MIT License. See `LICENSE` for the full text. The source imaging data remain subject to the applicable terms of their original repositories.
