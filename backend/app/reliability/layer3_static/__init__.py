# ruff: noqa: F401
"""
Layer 3 — Static analysis.

Runs inline during each build agent (agent calls this on its own output).
Detects common TypeScript/React patterns that cause runtime errors:
  - Null reference patterns
  - Unhandled promise rejections
  - Missing error boundaries
  - Zustand store mutation violations
  - Circular imports and missing files
  - Predicted runtime errors
"""

from app.reliability.layer3_static.ast_analyser import (
    ASTIssue,
    ASTReport,
    analyze_file,
)
from app.reliability.layer3_static.import_graph_resolver import (
    ImportGraph,
    build_import_graph,
)
from app.reliability.layer3_static.runtime_error_predictor import (
    PredictedError,
    predict_errors,
)

__all__ = [
    "ASTIssue",
    "ASTReport",
    "ImportGraph",
    "PredictedError",
    "analyze_file",
    "build_import_graph",
    "predict_errors",
]
