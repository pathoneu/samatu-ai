"""
V2.1 Interior analysis pipeline.
Multi-file, 4-phase: Phase1 → Phase2(parallel) → Phase3 → Phase4(Python).
"""
from .orchestrator import process_interior_project_v2_1

__all__ = ["process_interior_project_v2_1"]
