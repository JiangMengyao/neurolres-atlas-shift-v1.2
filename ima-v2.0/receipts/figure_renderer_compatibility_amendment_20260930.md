# Post-effect figure-renderer compatibility amendment

**Date:** 30 September 2026  
**Scope:** Figure 4, Figure 5, and Figure 6 rendering only

After the locked 762-case inference and comparative scoring were complete, the local PDF device used by the R figure scripts was found to depend on an unavailable X11/Cairo backend. The scripts were repaired to use the base R PDF device with an explicit Helvetica family. Figure 5 also received an explicit `inherit.aes = FALSE` mapping for its summary layers so that the supplied aggregate summary data were rendered against the intended axes.

This is a packaging and renderer-compatibility repair, not an analysis amendment. No case files, model weights, inference outputs, masks, denominators, estimands, model-selection decisions, statistical methods, or source-data CSV files changed. Figure 4 qualitative selection remained locked before comparative performance access. The affected figures were re-rendered from the unchanged source data, visually inspected page-by-page, and their output hashes are recorded in the figure render receipt and public qualitative receipt.

| Item | Frozen/protocol hash | Final post-effect hash | Interpretation |
|---|---|---|---|
| Figure 5/6 R renderer | `c3f2df91238e65cb0fbf9a157064cd575eeeb9a9f32d49c3d0ae78e7c6bcdfca` | `54b036cc89e31fb6ef2793a250ad55b8c5c633a1b2c1cb35fd007827371570d5` | PDF device and explicit summary-layer mappings only |
| Figure 4 R renderer | `9f6a6c04d15e79fe2bc93abd0d51e143794357cc197929ababe0642d1ac0b600` | `d59f8a00a4f6bbab3ae2406398f2d551fcd1b5eec0f1cd589b84606ea32535f1` | PDF device only |

The frozen E4 protocol remains unchanged. This record is included to make the post-effect renderer transition explicit rather than silently replacing a locked hash.
