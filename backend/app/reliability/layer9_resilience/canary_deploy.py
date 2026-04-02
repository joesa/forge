"""
Layer 9 — Canary deployment engine.

Implements phased traffic migration for new builds:
  Phase 1: Route 5% of traffic → check error rate after 60s
  Phase 2: Route 25% of traffic → check error rate after 60s
  Phase 3: Route 100% of traffic (full deploy)

Auto-rollback if error rate >= 0.1% at any phase.

In production, interacts with Cloudflare Traffic Manager for weighted
routing.  The traffic manager and error rate checker are injected via
protocols for testability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import structlog

logger = structlog.get_logger(__name__)

# Error threshold: if rate >= 0.1% at any phase, trigger rollback
ERROR_RATE_THRESHOLD = 0.001  # 0.1%

# Wait time between phases (seconds) — configurable for tests
DEFAULT_PHASE_WAIT_SECONDS = 60


# ── Types ────────────────────────────────────────────────────────────


class CanaryPhase(str, Enum):
    """Deployment phases."""

    PHASE_1 = "phase_1"  # 5% traffic
    PHASE_2 = "phase_2"  # 25% traffic
    PHASE_3 = "phase_3"  # 100% traffic
    ROLLED_BACK = "rolled_back"
    COMPLETED = "completed"


@dataclass
class PhaseResult:
    """Result of a single canary phase."""

    phase: CanaryPhase
    traffic_percent: int
    error_rate: float = 0.0
    passed: bool = False


@dataclass
class CanaryResult:
    """Outcome of the full canary deployment."""

    success: bool = False
    final_phase: CanaryPhase = CanaryPhase.PHASE_1
    phases: list[PhaseResult] = field(default_factory=list)
    rolled_back: bool = False
    error: str | None = None


# ── Protocols ────────────────────────────────────────────────────────


class TrafficManager(Protocol):
    """Protocol for routing traffic between builds."""

    async def set_traffic_split(
        self, build_id: str, project_id: str, percent: int
    ) -> bool:
        """Route ``percent`` of traffic to the new build.

        Returns True on success.
        """
        ...


class ErrorRateChecker(Protocol):
    """Protocol for checking current error rate."""

    async def get_error_rate(
        self, build_id: str, project_id: str
    ) -> float:
        """Return current error rate as a fraction (0.0–1.0)."""
        ...


class PhaseWaiter(Protocol):
    """Protocol for waiting between phases (injectable for tests)."""

    async def wait(self, seconds: float) -> None:
        ...


# ── Default implementations ─────────────────────────────────────────


class DefaultPhaseWaiter:
    """Production waiter — uses asyncio.sleep."""

    async def wait(self, seconds: float) -> None:
        import asyncio
        await asyncio.sleep(seconds)


# ── Canary phases definition ────────────────────────────────────────

_PHASES: list[tuple[CanaryPhase, int]] = [
    (CanaryPhase.PHASE_1, 5),
    (CanaryPhase.PHASE_2, 25),
    (CanaryPhase.PHASE_3, 100),
]


# ── Public API ───────────────────────────────────────────────────────


async def deploy_canary(
    build_id: str,
    project_id: str,
    *,
    traffic_manager: TrafficManager | None = None,
    error_checker: ErrorRateChecker | None = None,
    waiter: PhaseWaiter | None = None,
    phase_wait_seconds: float = DEFAULT_PHASE_WAIT_SECONDS,
) -> CanaryResult:
    """Execute a phased canary deployment.

    Parameters
    ----------
    build_id : str
        The new build to deploy.
    project_id : str
        The project this build belongs to.
    traffic_manager : TrafficManager | None
        Manages traffic splitting (Cloudflare Traffic Manager in prod).
    error_checker : ErrorRateChecker | None
        Checks error rate for the new build.
    waiter : PhaseWaiter | None
        Waits between phases (override for tests).
    phase_wait_seconds : float
        Seconds to wait between phases (default 60).

    Returns
    -------
    CanaryResult
        Result with phase-by-phase details and success status.
    """
    result = CanaryResult()

    if not build_id or not project_id:
        result.error = "build_id and project_id are required"
        return result

    if traffic_manager is None or error_checker is None:
        result.error = "traffic_manager and error_checker are required"
        return result

    actual_waiter = waiter or DefaultPhaseWaiter()

    try:
        for phase, percent in _PHASES:
            result.final_phase = phase

            # Set traffic split
            split_ok = await traffic_manager.set_traffic_split(
                build_id, project_id, percent
            )
            if not split_ok:
                result.error = f"Failed to set traffic split to {percent}%"
                logger.error(
                    "canary.traffic_split_failed",
                    phase=phase.value,
                    percent=percent,
                )
                return result

            logger.info(
                "canary.phase_started",
                phase=phase.value,
                percent=percent,
                build_id=build_id,
            )

            # Don't wait after the final phase (100%)
            if percent < 100:
                await actual_waiter.wait(phase_wait_seconds)

            # Check error rate
            error_rate = await error_checker.get_error_rate(
                build_id, project_id
            )

            phase_result = PhaseResult(
                phase=phase,
                traffic_percent=percent,
                error_rate=error_rate,
                passed=error_rate < ERROR_RATE_THRESHOLD,
            )
            result.phases.append(phase_result)

            if error_rate >= ERROR_RATE_THRESHOLD:
                # Auto-rollback: route 100% back to previous build
                logger.warning(
                    "canary.error_rate_exceeded",
                    phase=phase.value,
                    error_rate=error_rate,
                    threshold=ERROR_RATE_THRESHOLD,
                )

                await traffic_manager.set_traffic_split(
                    build_id, project_id, 0
                )

                result.rolled_back = True
                result.final_phase = CanaryPhase.ROLLED_BACK
                result.error = (
                    f"Error rate {error_rate:.4f} exceeded threshold "
                    f"{ERROR_RATE_THRESHOLD} at {phase.value} ({percent}%)"
                )
                return result

            logger.info(
                "canary.phase_passed",
                phase=phase.value,
                error_rate=error_rate,
            )

        # All phases passed
        result.success = True
        result.final_phase = CanaryPhase.COMPLETED

        logger.info(
            "canary.deployment_complete",
            build_id=build_id,
            project_id=project_id,
            total_phases=len(result.phases),
        )

    except Exception as exc:
        result.error = str(exc)
        result.rolled_back = True
        result.final_phase = CanaryPhase.ROLLED_BACK
        logger.error(
            "canary.failed",
            build_id=build_id,
            error=str(exc),
        )

        # Best-effort rollback on exception
        if traffic_manager is not None:
            try:
                await traffic_manager.set_traffic_split(
                    build_id, project_id, 0
                )
            except Exception:
                pass

    return result
