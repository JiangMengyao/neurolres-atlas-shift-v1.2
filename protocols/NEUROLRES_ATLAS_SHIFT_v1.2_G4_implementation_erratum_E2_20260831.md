# NEUROLRES-ATLAS-SHIFT v1.2 G4 implementation erratum E2

- Frozen at: `2026-08-31T03:24:59Z`
- Scope: prediction-ground-truth NIfTI header validation before official array-index scoring
- Triggered after: 240/762 isolated case results existed; Resume-1 worker index 240 stopped before writing a result
- Aggregate primary effect, confidence interval, p value, and G4 decision computed before E2: no
- Existing case results overwritten or deleted: no

## Trigger

The r1 formal scorer required the selected NIfTI affine matrices to differ by no more than `0.001 mm` and required identical axis-orientation codes before executing the official ISLES'26 metric functions. Resume-1 worker index 240 stopped with `GT_PRED_AFFINE_MISMATCH`. The immutable Resume-1 failure summary has SHA-256 `b060eb655a2e4b188a2bae80e16bbabd9d9a7501e0c9b6c998d98068fbf7a043`.

## Result-blind header diagnosis

An all-762 header-only scan loaded NIfTI headers but no voxel arrays and computed no effects. It found:

- prediction and ground-truth array shapes equal in 762/762;
- prediction and ground-truth voxel sizes equal in 762/762;
- prediction and source-T1 array shapes and orientations equal in 762/762;
- five selected-affine differences above `0.001 mm`;
- two selected-affine orientation-code differences;
- among the five flagged files, three have exactly or numerically equivalent alternative qform pairs, one differs by `0.0010757446 mm`, and one has a best qform difference of `1.875 mm` while retaining identical array shape and voxel size.

The official frozen ISLES'26 `eval_utils.py` accepts NumPy arrays, checks shape inside the relevant functions, and does not read NIfTI affine, qform, sform, or orientation metadata. The inherited v1.1 scoring script likewise compares the loaded voxel arrays directly and does not resample ground truth.

## Locked correction boundary

The revised scorer may change only the pre-metric geometry validation:

- require exact prediction-ground-truth array-shape equality;
- require voxel-size equality within absolute tolerance `1e-6`;
- record selected-affine delta and orientation equality as QC fields but do not use them to resample, rewrite, exclude, or fail a case;
- pass the unchanged array-index binary masks to the unchanged official ISLES'26 scorer;
- do not resample or modify ground truth or predictions;
- fail on shape or voxel-size mismatch, nonfinite data, invalid labels, or read error.

This E2 restores the inherited official array-index evaluation behavior. It does not authorize spatial registration, header repair, case exclusion, sample replacement, threshold changes, or post-hoc sensitivity analyses. The five header anomalies must be disclosed as a data-quality limitation.

The 240 existing case JSON files remain immutable. Any continuation must verify their combined filename-size-content manifest SHA-256 `97afa5eaf0d3afb4e28f75b731216bf946a92366414864261993a60fdfe6ea5b`, skip them without overwrite, and requires a separately recorded Resume-2 authorization.
