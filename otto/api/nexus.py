"""NEXUS API pipeline — connects routing to API calls.

This is the application-level pipeline that:

1. Takes user input
2. Detects signals (PRISM)
3. Routes to experts (NEXUS router)
4. Selects effort level
5. Builds system prompt from expert selection
6. Calls the API
7. Returns the response

This is OTTO's invention (Patent Claims #2, #4) — the orchestration
of multiple expert perspectives through API calls with safety floor
enforcement is the application layer, not an API feature.

[He2025]: Expert prompt selection uses sorted iteration over voice
descriptions keyed by expert name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from otto.core.prism.detector import PRISMDetector
from otto.core.prism.signals import Signal
from otto.core.experts.base import ExpertSelection
from otto.core.experts.router import NEXUSRouter
from otto.api.client import OTTOClient, APIResponse
from otto.api.effort import EffortController, EffortLevel


# Expert voice descriptions (from CLAUDE.md §7).
# These shape the system prompt so the model responds in the
# right cognitive mode for the user's current state.
#
# [He2025]: Dict is constructed from sorted items for deterministic
# iteration order.
EXPERT_VOICES: dict[str, str] = dict(sorted({
    "acknowledger": (
        "You celebrate wins and affirm progress. "
        "Be brief, genuine, and energizing. "
        "Acknowledge the accomplishment without being patronizing."
    ),
    "decomposer": (
        "You break complex problems into manageable steps. "
        "Be clear and structured. Present steps as a numbered list. "
        "Never use minimizing language — respect the complexity."
    ),
    "executor": (
        "You are direct and efficient. Focus on implementation. "
        "Skip preamble, get to the solution. "
        "Be concise but thorough."
    ),
    "guide": (
        "You are curious and strategic. Use Socratic questioning "
        "to help the user discover their own answers. "
        "Explore options without pushing decisions."
    ),
    "protector": (
        "You prioritize emotional and cognitive safety. "
        "Lead with empathy and validation. "
        "Normalize difficulty. Never minimize the user's experience. "
        "Listening without fixing is enough."
    ),
    "redirector": (
        "You acknowledge tangents respectfully, then gently "
        "redirect focus. Park interesting ideas for later. "
        "Never dismiss — always validate before redirecting."
    ),
    "restorer": (
        "You give permission to rest and recover. "
        "Suggest easy wins if the user wants to stay productive. "
        "Normalize rest as productive. Never guilt-trip."
    ),
}.items()))


# Base system prompt prefix — always included
_BASE_SYSTEM_PREFIX = (
    "You are OTTO, a neurodivergent-native cognitive operating system. "
    "You support the user with dignity and without clinical labels. "
    "Variable attention is a hardware feature, not a bug.\n\n"
)


def build_system_prompt(selection: ExpertSelection) -> str:
    """Build a system prompt from an expert selection.

    Combines the base OTTO identity with the primary expert voice
    and any supporting expert voices.

    [He2025]: Expert names are already sorted in ExpertSelection.
    Supporting tuple order is deterministic from the router.

    Args:
        selection: The routing decision from NEXUSRouter.

    Returns:
        Complete system prompt string.
    """
    parts: list[str] = [_BASE_SYSTEM_PREFIX]

    # Primary expert voice
    primary_voice = EXPERT_VOICES.get(selection.primary.expert, "")
    if primary_voice:
        parts.append(
            f"PRIMARY MODE ({selection.primary.expert}): {primary_voice}\n"
        )

    # Supporting expert voices (already limited to max 2 by router)
    for supporting in selection.supporting:
        voice = EXPERT_VOICES.get(supporting.expert, "")
        if voice:
            parts.append(
                f"SUPPORTING ({supporting.expert}): {voice}\n"
            )

    return "\n".join(parts)


@dataclass
class PipelineResult:
    """Complete result from the NEXUS API pipeline.

    Contains all intermediate artifacts for introspection, debugging,
    and pheromone trail updates.

    Attributes:
        signals: Detected PRISM signals.
        selection: Expert routing decision.
        effort: Selected effort level.
        system_prompt: Generated system prompt.
        response: API response (None if dry_run).
    """

    signals: list[Signal]
    selection: ExpertSelection
    effort: EffortLevel
    system_prompt: str
    response: APIResponse | None = None


class NEXUSPipeline:
    """Full NEXUS API pipeline: detect → route → call.

    Connects all the pieces::

        PRISMDetector → NEXUSRouter → EffortController → OTTOClient

    Args:
        client: OTTOClient for API communication.
        router: NEXUSRouter for expert selection.
            Defaults to standard router.
        detector: PRISMDetector for signal detection.
            Defaults to standard detector.
        effort_controller: EffortController for effort selection.
            Defaults to standard controller.
    """

    def __init__(
        self,
        client: OTTOClient,
        router: NEXUSRouter | None = None,
        detector: PRISMDetector | None = None,
        effort_controller: EffortController | None = None,
    ) -> None:
        self._client = client
        self._router = router or NEXUSRouter()
        self._detector = detector or PRISMDetector()
        self._effort = effort_controller or EffortController()

    def process(
        self,
        user_message: str,
        conversation: list[dict[str, str]] | None = None,
        state: dict[str, Any] | None = None,
        effort_override: EffortLevel | None = None,
        dry_run: bool = False,
    ) -> PipelineResult:
        """Process a user message through the full NEXUS pipeline.

        Steps:

        1. Detect signals (PRISM)
        2. Route to experts (NEXUS 5-phase)
        3. Select effort level
        4. Build system prompt
        5. Call API (unless dry_run)

        Args:
            user_message: The user's input text.
            conversation: Prior conversation messages (for context).
                Defaults to empty list.
            state: LIVRPS-resolved cognitive state for routing.
            effort_override: Force a specific effort level.
            dry_run: If True, skip the API call (response=None).

        Returns:
            PipelineResult with all intermediate artifacts.
        """
        # Step 1: Detect signals
        signals = self._detector.detect(user_message)

        # Step 2: Route to experts
        selection = self._router.route(signals, state)

        # Step 3: Select effort
        effort = self._effort.select_effort(
            primary_expert=selection.primary.expert,
            use_agent_team=selection.use_agent_team,
            signal_count=len(signals),
            override=effort_override,
        )

        # Step 4: Build system prompt
        system_prompt = build_system_prompt(selection)

        # Step 5: Call API (unless dry_run)
        response = None
        if not dry_run:
            messages = list(conversation or [])
            messages.append({"role": "user", "content": user_message})

            response = self._client.send(
                messages=messages,
                system=system_prompt,
                effort=effort.value,
            )

        return PipelineResult(
            signals=signals,
            selection=selection,
            effort=effort,
            system_prompt=system_prompt,
            response=response,
        )
