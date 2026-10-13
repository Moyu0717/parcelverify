"""
ParcelVerify — Agent Schemas
Owner: Role C (Investigation Agent)

Pydantic models for the investigation report structure.
These are used by the runner to validate model output.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from contracts import InvestigationReport, ToolCallRecord, InvestigationResult


# Re-export the models from contracts.py for convenience
__all__ = [
    "InvestigationReport",
    "ToolCallRecord",
    "InvestigationResult",
]
