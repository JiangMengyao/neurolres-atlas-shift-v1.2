# NEUROLRES-ATLAS-SHIFT v1.2 G4 implementation erratum E1

- Frozen at: `2026-08-31T02:49:38Z`
- Scope: formal G4 ground-truth storage-encoding validation only
- Triggered after: 56/762 isolated workers completed; worker index 56 stopped before writing a case result
- Aggregate primary effect, confidence interval, p value, and G4 decision computed before erratum: no
- Existing case results overwritten or deleted: no

## Trigger

The first frozen formal G4 scorer required raw ground-truth voxel values to be exactly `0` or `1` before applying the already inherited `>0.5` binary rule. Worker index 56 stopped with `GROUND_TRUTH_NOT_BINARY` before writing its case result. The immutable first-attempt public failure summary has SHA-256 `a1c2c67460cb5e9a72563e1ab1e1f7ecff67ab25d766ccae60fb7623c2eb2305`.

## Result-blind encoding diagnosis

An all-762 encoding-only scan recorded unique stored label values but did not count foreground voxels, calculate lesions, compare predictions with truth, compute effect metrics, aggregate centers, bootstrap, or evaluate G4. It found:

- 725 masks with values exactly `(0, 1)`;
- 32 masks with zero and one positive value between `0.9999999776482582` and `1.0000000591389835`, caused by NIfTI scaling precision;
- 5 valid empty masks containing only zero;
- 0 masks with nonfinite values, negative values, or multiple positive label values.

The failed worker's mask contained `(0, 1.0000000591389835)`. Thus the failure was caused by a stricter exact-value assertion newly added for v1.2 formal execution, not by a change in the inherited ground-truth definition.

## Locked correction boundary

The revised scorer may change only the raw-label validation:

- accept finite values within absolute tolerance `1e-6` of zero or one;
- continue to create the binary truth mask using the unchanged `>0.5` rule;
- accept an all-zero mask and retain it in the fixed denominator;
- fail on nonfinite, negative, intermediate, or multi-label values outside that tolerance.

The official ISLES'26 scorer, prediction files, probability reconstruction, endpoint, center macro, 46-center joint bootstrap, 10,000 repetitions, seed `260827`, confidence interval, p-value definition, G4 thresholds, fixed denominators, and Pilot-36 exclusion must not change.

The 56 existing case JSON files remain immutable. Any continuation must verify their combined filename-size-content manifest SHA-256 `3486f119be1c1366a02670a02899d513b16a9e471f4563b536b9c4937e8449c9`, skip them without overwrite, and requires a separately recorded resume authorization.
