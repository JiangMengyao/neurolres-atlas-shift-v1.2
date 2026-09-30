# IMA-UPGRADE-v2.0 SynthStroke storage clarification E3

- Recorded: 2026-09-29, after the three-case outcome-blinded feasibility run and
  before formal SynthStroke inference or any SynthStroke outcome scoring.
- Parent extension: `IMA_UPGRADE_v2.0_exploratory_SynthStroke_lock_E2_20260929.json`

The feasibility runner stored two complementary probability channels as float32.
For the formal run, the NPZ stores only the stroke foreground posterior as float16
under the key `foreground`; no spatial crop, thresholding, or probability
renormalization is applied at storage. The scorer accepts either the original
nnU-Net two-channel `softmax` representation or this single-channel `foreground`
representation and reconstructs the same foreground probability array.

This is a loss-bounded storage-format change only. It does not alter preprocessing,
model weights, inference, native-space inversion, the six-class argmax binary mask,
case inclusion, metrics, thresholds, or statistical analysis.
