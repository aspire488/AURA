"""Bootstrap the canonical AURA agents.

Importing this module registers all agents with the harness and prepares the
lifecycle manager for use by the application (e.g., during startup).
"""

from __future__ import annotations

import logging

from .manager import AgentLifecycleManager
from .orchestrator import OrchestratorAgent
from .research import ResearchAgent
from .knowledge import KnowledgeAgent
from .coding import CodingAgent
from .browser import BrowserAgent
from .automation import AutomationAgent
from .communication import CommunicationAgent
from .monitoring import MonitoringAgent
from .planning import PlanningAgent
from .identity import IdentityAgent
from .stewardship import StewardshipAgent

logger = logging.getLogger(__name__)

# Instantiate the lifecycle manager – a singleton for the process.
_lifecycle = AgentLifecycleManager()

def _register_all() -> None:
    agents = [
        ("orchestrator", OrchestratorAgent(), ["orchestrate"]),
        ("research", ResearchAgent(), ["search", "summarize"]),
        ("knowledge", KnowledgeAgent(), ["store_fact", "retrieve_fact"]),
        ("coding", CodingAgent(), ["generate_code", "run_code"]),
        ("browser", BrowserAgent(), ["open_url", "click", "type"]),
        ("automation", AutomationAgent(), ["run_workflow", "trigger"]),
        ("communication", CommunicationAgent(), ["send_message", "receive"]),
        ("monitoring", MonitoringAgent(), ["report_metrics", "health_check"]),
        ("planning", PlanningAgent(), ["create_plan", "update_plan"]),
        ("identity", IdentityAgent(), ["resolve_identity", "list_identities"]),
        ("stewardship", StewardshipAgent(), ["consolidate_memory", "purge"]),
    ]
    for name, agent, caps in agents:
        _lifecycle.register(name, agent, caps)
        logger.debug("Bootstrap registered agent %s", name)

# Auto‑run registration at import time.
_register_all()

# Expose lifecycle manager for the app to call during startup/shutdown.
_lifecycle_manager = _lifecycle
