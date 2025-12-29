"""Simulation package for client testing utility."""

from .scenarios import Scenario, ScenarioPreset, load_scenario, get_all_presets, get_preset_description
from .personas import ClientPersona, generate_persona
from .conversation_engine import ConversationEngine
from .intake_adapter import IntakeAdapter
from .client_simulator import ClientSimulator, SimulatorConfig

__all__ = [
    "Scenario",
    "ScenarioPreset",
    "load_scenario",
    "get_all_presets",
    "get_preset_description",
    "ClientPersona",
    "generate_persona",
    "ConversationEngine",
    "IntakeAdapter",
    "ClientSimulator",
    "SimulatorConfig",
]

