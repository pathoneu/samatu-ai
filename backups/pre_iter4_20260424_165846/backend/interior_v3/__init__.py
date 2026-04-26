"""
V3 pipeline — single Opus 4.7 call per project, few-shot prompted with the
5 training projects.

Philosophy:
- No fragmentation. One model, one call, sees the whole project at once.
- In-context learning from `training_dataset_v2.json` (4 of 5 projects as
  examples; 5th is the new one being estimated).
- Holdout validation: when testing P1 accuracy, P1 is NOT in the examples.
- Chain-of-thought: model must output a `reasoning` block per quantity.
"""
from .pipeline import process_interior_project_v3

__all__ = ["process_interior_project_v3"]
