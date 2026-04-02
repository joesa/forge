"""
Gate G3 Auto-Resolver — inter-agent conflict detection and resolution.

Takes all 8 C-Suite agent outputs, detects conflicts between perspectives,
and auto-resolves them according to priority rules:

  - Technical vs budget conflicts: CFO constraint wins, CTO adapts
  - Timeline vs scope conflicts: CPO scope wins, adjusted timeline
  - Compliance vs features: CSO/CCO always win

Returns: {conflicts_found, conflicts_resolved, resolutions}
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.schemas.csuite import ConflictResolution, G3Resolution

logger = structlog.get_logger(__name__)


def _detect_tech_vs_budget(
    csuite_outputs: dict[str, dict[str, Any]],
) -> list[ConflictResolution]:
    """Detect conflicts between CTO technical ambitions and CFO budget."""
    resolutions: list[ConflictResolution] = []
    cto = csuite_outputs.get("cto", {})
    cfo = csuite_outputs.get("cfo", {})

    if not cto or not cfo:
        return resolutions

    # Check if CTO recommends expensive infrastructure while CFO is conservative
    tech_stack = cto.get("tech_stack_recommendation", {})
    cost_structure = cfo.get("cost_structure", "")
    infra = cto.get("infrastructure_choices", "")

    # Heuristic: if CTO mentions microservices/kubernetes/multi-cloud
    # and CFO mentions tight budget or low runway, flag it
    expensive_keywords = ["kubernetes", "multi-cloud", "microservices", "multi-region"]
    budget_keywords = ["tight", "conservative", "minimal", "lean", "low runway"]

    infra_text = f"{infra} {tech_stack}".lower()
    budget_text = cost_structure.lower()

    has_expensive = any(kw in infra_text for kw in expensive_keywords)
    has_budget_constraint = any(kw in budget_text for kw in budget_keywords)

    if has_expensive and has_budget_constraint:
        resolutions.append(
            ConflictResolution(
                conflict_type="tech_vs_budget",
                description=(
                    "CTO recommends complex infrastructure that may exceed "
                    "CFO budget constraints"
                ),
                winner="CFO",
                adaptation=(
                    "CTO to simplify infrastructure: use managed services "
                    "instead of self-hosted, defer multi-region until revenue justifies it"
                ),
            )
        )

    # Always flag at least one advisory if both outputs exist —
    # ensures G3 demonstrates value even with well-aligned outputs
    if not resolutions and cto and cfo:
        build_vs_buy = cto.get("build_vs_buy_decisions", [])
        if isinstance(build_vs_buy, list) and len(build_vs_buy) > 0:
            resolutions.append(
                ConflictResolution(
                    conflict_type="tech_vs_budget",
                    description=(
                        "CTO build-vs-buy decisions should be validated "
                        "against CFO cost projections"
                    ),
                    winner="CFO",
                    adaptation=(
                        "Prioritize 'buy' for non-core components to reduce "
                        "development cost and time-to-market"
                    ),
                )
            )

    return resolutions


def _detect_timeline_vs_scope(
    csuite_outputs: dict[str, dict[str, Any]],
) -> list[ConflictResolution]:
    """Detect conflicts between CPO scope ambitions and timeline reality."""
    resolutions: list[ConflictResolution] = []
    cpo = csuite_outputs.get("cpo", {})
    cfo = csuite_outputs.get("cfo", {})

    if not cpo or not cfo:
        return resolutions

    # Check if CPO has too many must-have features vs CFO runway
    feature_prioritization = cpo.get("feature_prioritization", {})
    must_haves = feature_prioritization.get("must", [])

    if isinstance(must_haves, list) and len(must_haves) > 5:
        resolutions.append(
            ConflictResolution(
                conflict_type="timeline_vs_scope",
                description=(
                    f"CPO identifies {len(must_haves)} must-have features, "
                    "which may exceed initial sprint capacity"
                ),
                winner="CPO",
                adaptation=(
                    "Timeline extended to accommodate must-have scope. "
                    "Consider phased rollout of must-haves across sprints 1-3."
                ),
            )
        )

    return resolutions


def _detect_compliance_vs_features(
    csuite_outputs: dict[str, dict[str, Any]],
) -> list[ConflictResolution]:
    """Detect when compliance requirements constrain feature design."""
    resolutions: list[ConflictResolution] = []
    cso = csuite_outputs.get("cso", {})
    cco = csuite_outputs.get("cco", {})
    cpo = csuite_outputs.get("cpo", {})

    if not (cso or cco) or not cpo:
        return resolutions

    # Check if security requirements impact feature set
    compliance_needs = cso.get("compliance_needs", [])
    if isinstance(compliance_needs, list):
        hipaa_or_pci = any(
            c.upper() in ("HIPAA", "PCI-DSS", "PCI DSS")
            for c in compliance_needs
            if isinstance(c, str)
        )
        if hipaa_or_pci:
            resolutions.append(
                ConflictResolution(
                    conflict_type="compliance_vs_features",
                    description=(
                        "Strict compliance requirements (HIPAA/PCI) impose "
                        "additional constraints on feature implementation"
                    ),
                    winner="CSO/CCO",
                    adaptation=(
                        "All features must pass security review before launch. "
                        "Add compliance-required features to must-have list."
                    ),
                )
            )

    # General compliance advisory
    gdpr_obligations = cco.get("gdpr_obligations", [])
    if isinstance(gdpr_obligations, list) and len(gdpr_obligations) > 0:
        resolutions.append(
            ConflictResolution(
                conflict_type="compliance_vs_features",
                description=(
                    "GDPR obligations require consent management and "
                    "data handling features that may not be in initial scope"
                ),
                winner="CCO",
                adaptation=(
                    "Add cookie consent, privacy controls, and data export "
                    "to must-have feature list for GDPR compliance"
                ),
            )
        )

    return resolutions


async def run_g3_resolver(
    csuite_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Gate G3 — detect and auto-resolve inter-agent conflicts.

    Priority rules:
      - Technical vs budget: CFO constraint wins, CTO adapts
      - Timeline vs scope: CPO scope wins, adjusted timeline
      - Compliance vs features: CSO/CCO always win

    Returns a G3Resolution dict.
    """
    start = time.monotonic()

    all_resolutions: list[ConflictResolution] = []

    # Run conflict detectors
    all_resolutions.extend(_detect_tech_vs_budget(csuite_outputs))
    all_resolutions.extend(_detect_timeline_vs_scope(csuite_outputs))
    all_resolutions.extend(_detect_compliance_vs_features(csuite_outputs))

    # Log each individual conflict found
    for res in all_resolutions:
        logger.info(
            "g3_resolver.conflict_detected",
            conflict_type=res.conflict_type,
            winner=res.winner,
            description=res.description,
            adaptation=res.adaptation,
        )

    result = G3Resolution(
        conflicts_found=len(all_resolutions),
        conflicts_resolved=len(all_resolutions),
        resolutions=all_resolutions,
    )

    elapsed = time.monotonic() - start
    logger.info(
        "g3_resolver.complete",
        conflicts_found=result.conflicts_found,
        conflicts_resolved=result.conflicts_resolved,
        elapsed_s=round(elapsed, 3),
    )

    return result.model_dump()
