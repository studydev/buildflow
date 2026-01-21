"""
Pipelines package for Azure Container Apps Jobs execution.

This package contains the pipeline infrastructure per Constitution v2.0.0:
- BasePipeline: Abstract base class with lifecycle hooks
- Pipeline implementations: Analysis, Enrichment, Localization, etc.
- Runner: Container Apps Job entry point
"""

from app.pipelines.base import BasePipeline, PipelineResult

__all__ = [
    "BasePipeline",
    "PipelineResult",
]
