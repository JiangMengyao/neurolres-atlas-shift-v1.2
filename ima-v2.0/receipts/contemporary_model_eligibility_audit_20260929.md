# Contemporary comparator eligibility audit

Audit date: 2026-09-29, before formal comparator outcome scoring.

## Inclusion logic

A runnable comparator required a documented T1-weighted stroke-lesion task, public
weights, a reproducible inference interface, and no known case-level overlap between
its training resource and the fixed 762-case formal evaluation cohort. Literature
scores from different splits were not treated as head-to-head evidence.

## Decisions

1. **MAPPING Default, DiceTopK10, and residual nnU-Net (2022): technically eligible.** The
   official repository and five-fold weights were available. Its 655-case ATLAS R2
   resource exactly matched the audited release training stratum and had zero
   identifier overlap with the 762 formal cases. These models use the same inference
   pipeline, so loss-function and architecture comparisons have low implementation
   confounding. Outcome-blinded timing of the five-fold DiceTopK10 pipeline implied
   more than 250 wall-clock hours for both full 762-case variant runs on the
   available CPU-only host. Under the pre-result feasibility amendment, only the
   already complete default model was retained for formal analysis; neither variant
   was scored or reported as performance evidence.
2. **SynthStroke Synth (2025): eligible as an exploratory out-of-family comparator.**
   The MELBA article, source repository, model card, and immutable Hugging Face
   revision were available. The publication used the 655-case ATLAS R2 resource
   (419/105/131 train/validation/test) together with OASIS-3-derived synthetic images.
   The audited 655-case resource had zero identifier overlap with the formal 762.
   Because its preprocessing and six-class MONAI output differ from MAPPING, it is
   descriptive and is not added to the two-test primary Holm family.
3. **MSCSA (ISBI 2025): not executable.** The official repository exposed training
   and evaluation code but no retrievable pretrained checkpoint in its recursive
   file tree on the audit date. Five-fold retraining was infeasible on the available
   CPU-only host and would not reproduce the published run exactly. It remains a
   contemporary related-work citation, not a numerical comparator.
4. **BrainSegFounder ATLAS-finetune: ineligible.** The public model card states that
   ATLAS fine-tuning used 1,271 subjects. That population extends beyond the audited
   655-case training resource, so overlap with the fixed formal cohort cannot be
   excluded.
5. **ISLES26 center-grouped nnU-Net (2026): ineligible.** Its model card states that
   training used the full 1,452-case public ISLES26 release, which contains the cases
   assigned to the present formal evaluation. Using it would directly violate the
   training/evaluation independence gate.

## Primary sources

- MAPPING: https://github.com/King-HAW/ATLAS-R2-Docker-Submission and https://arxiv.org/abs/2211.15486
- SynthStroke: https://doi.org/10.59275/j.melba.2025-f3g6 and https://huggingface.co/liamchalcroft/synthstroke-synth
- MSCSA: https://doi.org/10.1109/ISBI60581.2025.10980930 and https://github.com/nadluru/StrokeLesSeg
- BrainSegFounder: https://huggingface.co/smilelab/BrainSegFounder
- ISLES26 center-grouped model: https://huggingface.co/sbollmann/isles26-nnunet-d507-topk10
