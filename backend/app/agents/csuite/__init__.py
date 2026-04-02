# ruff: noqa: F401
"""
C-Suite executive agents — 8 parallel analysts for Stage 2.

Each agent analyzes the user's idea from a different executive perspective.
All run concurrently via asyncio.gather in the Stage 2 graph node.
"""

from app.agents.csuite.ceo_agent import run_ceo_agent
from app.agents.csuite.cto_agent import run_cto_agent
from app.agents.csuite.cdo_agent import run_cdo_agent
from app.agents.csuite.cmo_agent import run_cmo_agent
from app.agents.csuite.cpo_agent import run_cpo_agent
from app.agents.csuite.cso_agent import run_cso_agent
from app.agents.csuite.cco_agent import run_cco_agent
from app.agents.csuite.cfo_agent import run_cfo_agent

# Agent name → run function mapping
CSUITE_AGENT_MAP = {
    "ceo": run_ceo_agent,
    "cto": run_cto_agent,
    "cdo": run_cdo_agent,
    "cmo": run_cmo_agent,
    "cpo": run_cpo_agent,
    "cso": run_cso_agent,
    "cco": run_cco_agent,
    "cfo": run_cfo_agent,
}

CSUITE_AGENT_NAMES = tuple(CSUITE_AGENT_MAP.keys())

__all__ = [
    "run_ceo_agent",
    "run_cto_agent",
    "run_cdo_agent",
    "run_cmo_agent",
    "run_cpo_agent",
    "run_cso_agent",
    "run_cco_agent",
    "run_cfo_agent",
    "CSUITE_AGENT_MAP",
    "CSUITE_AGENT_NAMES",
]
