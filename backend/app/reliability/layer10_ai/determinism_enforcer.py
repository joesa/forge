"""
Layer 10 — Determinism enforcer.

Wrapper that ensures all build agent LLM calls use temperature=0 and
seed=42.  Implements AGENTS.md rule #4: "Build agents: temperature=0,
fixed seed (deterministic)".

If a decorated function is called with temperature != 0, the enforcer
overrides it and logs a warning (indicates an agent bug).
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Coroutine, TypeVar

import structlog

logger = structlog.get_logger(__name__)

# Enforced values (AGENTS.md rule #4)
ENFORCED_TEMPERATURE = 0.0
ENFORCED_SEED = 42

F = TypeVar("F", bound=Callable[..., Coroutine[Any, Any, Any]])


def enforce_determinism(fn: F) -> F:
    """Decorator that forces temperature=0 and seed=42 on LLM calls.

    Intercepts any call where ``temperature`` is a keyword argument
    and overrides it to 0.0 if different.  Also injects ``seed=42``
    if the function accepts a ``seed`` parameter.

    Parameters
    ----------
    fn : Callable
        The async function to wrap (typically an ai_router.complete call).

    Returns
    -------
    Callable
        Wrapped function with determinism enforcement.

    Example
    -------
    ::

        @enforce_determinism
        async def generate(prompt: str, temperature: float = 0.7) -> str:
            ...

        # Even if called with temperature=0.7, it will be forced to 0.0
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Override temperature if present and non-zero
        if "temperature" in kwargs:
            original_temp = kwargs["temperature"]
            if original_temp != ENFORCED_TEMPERATURE:
                logger.warning(
                    "determinism_enforcer.temperature_overridden",
                    original=original_temp,
                    enforced=ENFORCED_TEMPERATURE,
                    function=fn.__qualname__,
                )
                kwargs["temperature"] = ENFORCED_TEMPERATURE

        # Inject seed if the function accepts it
        import inspect
        sig = inspect.signature(fn)
        if "seed" in sig.parameters and "seed" not in kwargs:
            kwargs["seed"] = ENFORCED_SEED
        elif "seed" in kwargs and kwargs["seed"] != ENFORCED_SEED:
            logger.warning(
                "determinism_enforcer.seed_overridden",
                original=kwargs["seed"],
                enforced=ENFORCED_SEED,
                function=fn.__qualname__,
            )
            kwargs["seed"] = ENFORCED_SEED

        return await fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def enforce_determinism_on_router(ai_router: Any) -> Any:
    """Wrap an AI router's complete() method with determinism enforcement.

    Parameters
    ----------
    ai_router : AIRouterProtocol
        The AI router instance to wrap.

    Returns
    -------
    AIRouterProtocol
        The same router with its complete() method wrapped.
    """
    if hasattr(ai_router, "complete"):
        original_complete = ai_router.complete

        @functools.wraps(original_complete)
        async def enforced_complete(*args: Any, **kwargs: Any) -> Any:
            # Override temperature
            if "temperature" in kwargs:
                original_temp = kwargs["temperature"]
                if original_temp != ENFORCED_TEMPERATURE:
                    logger.warning(
                        "determinism_enforcer.router_temperature_overridden",
                        original=original_temp,
                        enforced=ENFORCED_TEMPERATURE,
                    )
                    kwargs["temperature"] = ENFORCED_TEMPERATURE

            # Inject seed only if the underlying method accepts it
            import inspect
            sig = inspect.signature(original_complete)
            if "seed" in sig.parameters:
                if "seed" not in kwargs:
                    kwargs["seed"] = ENFORCED_SEED
                elif kwargs["seed"] != ENFORCED_SEED:
                    logger.warning(
                        "determinism_enforcer.router_seed_overridden",
                        original=kwargs["seed"],
                        enforced=ENFORCED_SEED,
                    )
                    kwargs["seed"] = ENFORCED_SEED
            # Also handle **kwargs-accepting functions
            elif "seed" in kwargs and kwargs["seed"] != ENFORCED_SEED:
                logger.warning(
                    "determinism_enforcer.router_seed_overridden",
                    original=kwargs["seed"],
                    enforced=ENFORCED_SEED,
                )
                kwargs["seed"] = ENFORCED_SEED

            return await original_complete(*args, **kwargs)

        ai_router.complete = enforced_complete

    return ai_router
