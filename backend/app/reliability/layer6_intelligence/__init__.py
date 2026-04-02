# ruff: noqa: F401
"""
Layer 6 — Build intelligence.

Semantic caching, build memory, error boundary injection, and incremental
build detection.  Learns from past builds to improve future generation.
"""

from app.reliability.layer6_intelligence.build_cache import (
    CacheResult,
    check_cache,
    store_in_cache,
)
from app.reliability.layer6_intelligence.build_memory import (
    BuildMemory,
    get_relevant_memories,
    record_successful_build,
)
from app.reliability.layer6_intelligence.error_boundary_injector import (
    inject_error_boundaries,
)
from app.reliability.layer6_intelligence.incremental_build import (
    detect_changed_modules,
)

__all__ = [
    "BuildMemory",
    "CacheResult",
    "check_cache",
    "detect_changed_modules",
    "get_relevant_memories",
    "inject_error_boundaries",
    "record_successful_build",
    "store_in_cache",
]
