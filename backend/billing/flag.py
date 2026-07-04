"""Single source of truth for the billing kill-switch.

BILLING_ENABLED must be exactly "1" to enable. Any other value (unset, "0",
"true", "") = OFF. OFF is the launch default and reproduces pre-billing
behavior everywhere this is checked.
"""
from __future__ import annotations
import os


def billing_enabled() -> bool:
    return os.environ.get("BILLING_ENABLED", "0") == "1"
