"""Centralized config: model names, severity vocabulary, feature flags.

Everything that used to be a magic string scattered across modules.
"""

import os
from typing import Literal

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004")

# Canonical severity vocabulary. Anything else is invalid.
Severity = Literal["low", "medium", "high", "critical"]
SEVERITY_LEVELS: tuple[Severity, ...] = ("low", "medium", "high", "critical")
SEVERITY_ACTION_THRESHOLD: tuple[Severity, ...] = ("high", "critical")

# Composio civic-action cooldown (seconds). Same (agent, issue_title) won't
# create another GitHub issue inside this window.
CIVIC_ACTION_COOLDOWN_SECONDS = int(os.getenv("CIVIC_ACTION_COOLDOWN_SECONDS", "3600"))

# Agent loop intervals
AGENT_LOOP_INTERVAL = int(os.getenv("AGENT_LOOP_INTERVAL", "60"))
NEWS_LOOP_INTERVAL = int(os.getenv("NEWS_LOOP_INTERVAL", "90"))
