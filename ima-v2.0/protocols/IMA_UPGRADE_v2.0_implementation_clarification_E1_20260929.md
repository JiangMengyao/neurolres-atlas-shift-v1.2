# IMA-UPGRADE-v2.0 implementation clarification E1

- Recorded: 2026-09-29, before comparator inference completed and before any comparator outcome was scored.
- Parent lock: `IMA_UPGRADE_v2.0_multimodel_uncertainty_lock_20260929.json`
- Parent lock SHA-256: `4a6a1421310231ac21ae251a8aff7c1e22ef8bbedbb01a7d3e43c1dfafaf3b21`

## Clarification

The phrase "paired 46-center union bootstrap" in `comparative_analysis.primary_interval`
is internally inconsistent with the two locked primary upgrade estimands, both of which
are defined within `R3_NEW`. For each comparator-minus-default estimand in `R3_NEW`,
the implementation therefore resamples the 26 `R3_NEW` centers with replacement and
preserves within-center model pairing. The 46-center union bootstrap remains the
implementation for each model's `R2_TEST - R3_NEW` source-stratum contrast, exactly as
in the original primary analysis.

No model, case, endpoint, threshold, multiplicity rule, seed, or stop rule is changed.
Holm adjustment remains prespecified across the two comparator-versus-default tests in
`R3_NEW`. This clarification may not be revised after comparator outcomes are opened.

