# Comparator feasibility note

This note records the outcome-blinded eligibility and compute-feasibility decisions made before formal comparator scoring.

The official MAPPING repository and alternative five-fold weights were ultimately retrieved and hashed. A single DiceTopK10 feasibility case passed shape and output-integrity checks, but measured CPU timing projected more than 250 wall-clock hours for complete DiceTopK10 and residual-nnU-Net runs across the fixed 762 cases. Under the prespecified feasibility amendment, those variants were excluded before any formal ground-truth scoring. No literature score from a different split was substituted.

SynthStroke (2025) supplied a public immutable checkpoint and a reproducible whole-volume inference path. An outcome-blinded three-case pilot passed native-shape restoration and nonempty-output checks within the available compute envelope. SynthStroke was therefore retained as a methodologically distinct contemporary comparator and run on the same 762 cases as the reference model.

MSCSA was not executable because its official repository did not expose a retrievable pretrained checkpoint. BrainSegFounder was ineligible because its model card reported ATLAS fine-tuning on 1,271 subjects, so overlap with the formal cohort could not be excluded. The ISLES26 center-grouped model was ineligible because its documented training set included the formal cases directly.

These decisions concern executable model pipelines. The study does not interpret their performance differences as isolated effects of architecture, loss function, or synthetic training.
