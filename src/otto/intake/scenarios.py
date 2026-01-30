"""
Personality Intake Scenarios

Each scenario reveals personality traits without clinical language.
The user experiences choices, not assessments.

Design principles:
- No right or wrong answers
- Human language, not diagnostic
- Scenarios feel like conversations, not tests
- Each choice maps to USD profile attributes
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class TraitCategory(Enum):
    """Categories of traits we're detecting (internal only, never shown to user)"""
    CHRONOTYPE = "chronotype"
    WORK_STYLE = "work_style"
    STRESS_RESPONSE = "stress_response"
    PROTECTION_PREFERENCE = "protection_preference"
    RECOVERY_STYLE = "recovery_style"
    ENERGY_PATTERN = "energy_pattern"
    SOCIAL_BATTERY = "social_battery"


@dataclass
class Choice:
    """A single choice in a scenario"""
    text: str
    trait_mappings: dict[str, float | str]  # attribute -> value
    follow_up: str | None = None  # Optional OTTO response after selection


@dataclass
class Scenario:
    """A single intake scenario"""
    id: str
    category: TraitCategory
    setup: str  # The scene-setting text
    otto_says: str  # What OTTO asks
    choices: list[Choice]
    ascii_art: str | None = None  # Optional visual element


@dataclass
class ScenarioResult:
    """Result of completing a scenario"""
    scenario_id: str
    choice_index: int
    trait_mappings: dict[str, float | str]


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

SCENARIOS: list[Scenario] = [
    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 1: Chronotype Detection
    # ─────────────────────────────────────────────────────────────────────────────
    Scenario(
        id="chronotype_night",
        category=TraitCategory.CHRONOTYPE,
        ascii_art="""
    ┌─────────────────────────────────────────┐
    │                 🌙                       │
    │              ╭──────╮                   │
    │              │ 11:00│                   │
    │              │  PM  │                   │
    │              ╰──────╯                   │
    │         ░░░░░░░░░░░░░░░░░              │
    └─────────────────────────────────────────┘
        """,
        setup="It's 11 PM. You're still at your desk.",
        otto_says="What does this time of night usually feel like for you?",
        choices=[
            Choice(
                text="This is when I come alive. Night is my time.",
                trait_mappings={
                    "chronotype": "night_owl",
                    "peak_hours": [21, 22, 23, 0, 1],
                    "recovery_hours": [6, 7, 8, 9, 10],
                },
                follow_up="Night owl noted. I'll learn not to push morning tasks."
            ),
            Choice(
                text="I'm forcing myself to stay up. Should've slept hours ago.",
                trait_mappings={
                    "chronotype": "early_bird",
                    "peak_hours": [6, 7, 8, 9, 10],
                    "recovery_hours": [21, 22, 23, 0],
                },
                follow_up="Early riser. I'll protect your mornings."
            ),
            Choice(
                text="Depends on the day. Sometimes wired, sometimes crashing.",
                trait_mappings={
                    "chronotype": "variable",
                    "peak_hours": [],
                    "recovery_hours": [],
                },
                follow_up="Variable energy. I'll track patterns over time."
            ),
        ]
    ),

    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 2: Work Style
    # ─────────────────────────────────────────────────────────────────────────────
    Scenario(
        id="work_style_depth",
        category=TraitCategory.WORK_STYLE,
        ascii_art="""
    ┌─────────────────────────────────────────┐
    │                                         │
    │    ████████████████░░░░  Task A         │
    │                                         │
    │    ████░░░░░░░░░░░░░░░░  Task B         │
    │                                         │
    │    ░░░░░░░░░░░░░░░░░░░░  Task C         │
    │                                         │
    └─────────────────────────────────────────┘
        """,
        setup="You have three tasks today. All important, none urgent.",
        otto_says="How do you naturally approach them?",
        choices=[
            Choice(
                text="One at a time. Deep into A, then B, then C.",
                trait_mappings={
                    "work_style": "deep_work",
                    "focus_duration_minutes": 90,
                    "context_switch_cost": 0.8,
                },
                follow_up="Deep worker. I'll protect your focus blocks."
            ),
            Choice(
                text="Bounce between them. A bit of A, some B, back to A.",
                trait_mappings={
                    "work_style": "task_switcher",
                    "focus_duration_minutes": 25,
                    "context_switch_cost": 0.2,
                },
                follow_up="Switcher. I'll help you keep track of where you were."
            ),
            Choice(
                text="Intense bursts on whatever grabs me, then crash.",
                trait_mappings={
                    "work_style": "burst",
                    "focus_duration_minutes": 180,
                    "context_switch_cost": 0.9,
                },
                follow_up="Burst worker. I'll watch for the crash."
            ),
        ]
    ),

    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 3: Stress Response
    # ─────────────────────────────────────────────────────────────────────────────
    Scenario(
        id="stress_inbox",
        category=TraitCategory.STRESS_RESPONSE,
        ascii_art="""
    ┌─────────────────────────────────────────┐
    │                                         │
    │    ╔═══════════════════════════════╗    │
    │    ║  📧 INBOX              (47)   ║    │
    │    ╠═══════════════════════════════╣    │
    │    ║  ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■   ║    │
    │    ║  ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■   ║    │
    │    ╚═══════════════════════════════╝    │
    │                                         │
    └─────────────────────────────────────────┘
        """,
        setup="You open your inbox. 47 unread messages.",
        otto_says="A wave of something hits you. What is it?",
        choices=[
            Choice(
                text="Dread. I want to close the laptop and pretend I didn't see.",
                trait_mappings={
                    "stress_response": "avoid",
                    "overwhelm_threshold": 0.4,
                },
                follow_up="Avoidance pattern. I'll help break things into smaller pieces."
            ),
            Choice(
                text="Challenge accepted. Let me tear through these.",
                trait_mappings={
                    "stress_response": "confront",
                    "overwhelm_threshold": 0.8,
                },
                follow_up="Confronter. I'll stay out of your way when you're charging."
            ),
            Choice(
                text="Overwhelm. I need to process this feeling before I can act.",
                trait_mappings={
                    "stress_response": "process",
                    "overwhelm_threshold": 0.5,
                },
                follow_up="Processor. I'll give you space before jumping to solutions."
            ),
            Choice(
                text="Meh. I'll deal with it later. Not my problem right now.",
                trait_mappings={
                    "stress_response": "deflect",
                    "overwhelm_threshold": 0.7,
                },
                follow_up="Deflector. I'll remind you gently when things pile up."
            ),
        ]
    ),

    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 4: Protection Preference
    # ─────────────────────────────────────────────────────────────────────────────
    Scenario(
        id="protection_style",
        category=TraitCategory.PROTECTION_PREFERENCE,
        ascii_art="""
    ┌─────────────────────────────────────────┐
    │                                         │
    │           ╭────────────────╮            │
    │           │  ○  ○          │            │
    │           │   \\_/          │            │
    │           │                │            │
    │           │  4 hours...    │            │
    │           ╰────────────────╯            │
    │                                         │
    └─────────────────────────────────────────┘
        """,
        setup="You've been working for 4 hours straight. I notice you're getting tired.",
        otto_says="What would you want me to do?",
        choices=[
            Choice(
                text="Tell me to stop. Be firm. I need someone to say no.",
                trait_mappings={
                    "protection_firmness": 0.9,
                    "allow_override": False,
                    "override_cooldown_minutes": 60,
                },
                follow_up="Firm guardian it is. I'll hold the line when you can't."
            ),
            Choice(
                text="Mention it gently, but don't block me. I'll decide.",
                trait_mappings={
                    "protection_firmness": 0.3,
                    "allow_override": True,
                    "override_cooldown_minutes": 15,
                },
                follow_up="Gentle nudges. I'll suggest, never block."
            ),
            Choice(
                text="Learn my patterns. Sometimes I need to push through.",
                trait_mappings={
                    "protection_firmness": 0.5,
                    "allow_override": True,
                    "override_cooldown_minutes": 30,
                },
                follow_up="Adaptive. I'll learn when pushing works and when it doesn't."
            ),
            Choice(
                text="Stay out of it. I know my limits.",
                trait_mappings={
                    "protection_firmness": 0.0,
                    "allow_override": True,
                    "override_cooldown_minutes": 0,
                },
                follow_up="Hands off. I'll be here if you need me, silent otherwise."
            ),
        ]
    ),

    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 5: Recovery Style
    # ─────────────────────────────────────────────────────────────────────────────
    Scenario(
        id="recovery_method",
        category=TraitCategory.RECOVERY_STYLE,
        ascii_art="""
    ┌─────────────────────────────────────────┐
    │                                         │
    │    ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░  ENERGY        │
    │                                         │
    │         You've hit a wall.              │
    │                                         │
    └─────────────────────────────────────────┘
        """,
        setup="You've hit a wall. The work isn't flowing anymore.",
        otto_says="What usually helps?",
        choices=[
            Choice(
                text="Being alone. Quiet. No input.",
                trait_mappings={
                    "preferred_recovery": "solitude",
                    "recovery_social_need": 0.0,
                },
                follow_up="Solitude recharges you. I'll protect your quiet time."
            ),
            Choice(
                text="Talking to someone. Getting out of my head.",
                trait_mappings={
                    "preferred_recovery": "social",
                    "recovery_social_need": 0.9,
                },
                follow_up="Social recharge. I'll know when to suggest reaching out."
            ),
            Choice(
                text="Movement. A walk, exercise, anything physical.",
                trait_mappings={
                    "preferred_recovery": "activity",
                    "recovery_social_need": 0.3,
                },
                follow_up="Movement helps. I'll remind you that your body exists."
            ),
            Choice(
                text="Sleep. Just... sleep.",
                trait_mappings={
                    "preferred_recovery": "rest",
                    "recovery_social_need": 0.0,
                },
                follow_up="Rest is repair. I'll never make you feel bad for stopping."
            ),
        ]
    ),

    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 6: Decision Fatigue
    # ─────────────────────────────────────────────────────────────────────────────
    Scenario(
        id="decision_fatigue",
        category=TraitCategory.ENERGY_PATTERN,
        ascii_art="""
    ┌─────────────────────────────────────────┐
    │                                         │
    │   "What do you want for dinner?"        │
    │                                         │
    │      A          B          C            │
    │     [ ]        [ ]        [ ]           │
    │      D          E          F            │
    │     [ ]        [ ]        [ ]           │
    │      G          H          I            │
    │     [ ]        [ ]        [ ]           │
    │                                         │
    └─────────────────────────────────────────┘
        """,
        setup='Someone asks: "What do you want for dinner?"',
        otto_says="After a long day, this question feels like...",
        choices=[
            Choice(
                text="Impossible. Just pick something. I can't decide anything else.",
                trait_mappings={
                    "decision_fatigue_sensitivity": 0.9,
                    "max_daily_decisions": 10,
                },
                follow_up="Decision fatigue is real. I'll limit your choices when needed."
            ),
            Choice(
                text="Fine. It's just dinner. I can handle it.",
                trait_mappings={
                    "decision_fatigue_sensitivity": 0.3,
                    "max_daily_decisions": 50,
                },
                follow_up="You handle decisions well. I won't over-protect."
            ),
            Choice(
                text="Depends how the day went. Sometimes easy, sometimes impossible.",
                trait_mappings={
                    "decision_fatigue_sensitivity": 0.6,
                    "max_daily_decisions": 25,
                },
                follow_up="Variable tolerance. I'll read the room."
            ),
        ]
    ),

    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 7: Flow Interruption
    # ─────────────────────────────────────────────────────────────────────────────
    Scenario(
        id="flow_interruption",
        category=TraitCategory.WORK_STYLE,
        ascii_art="""
    ┌─────────────────────────────────────────┐
    │                                         │
    │  ████████████████████████████  FLOW     │
    │                                         │
    │         *ping* - notification           │
    │                                         │
    │  ████████████░░░░░░░░░░░░░░░░  ???      │
    │                                         │
    └─────────────────────────────────────────┘
        """,
        setup="You're deep in focus. A notification pops up.",
        otto_says="What happens next?",
        choices=[
            Choice(
                text="The thread is gone. I've lost it. It'll take forever to get back.",
                trait_mappings={
                    "interruption_recovery_minutes": 30,
                    "notification_sensitivity": 0.9,
                },
                follow_up="Interruptions are costly for you. I'll help guard focus time."
            ),
            Choice(
                text="Annoying, but I can get back. Give me a minute.",
                trait_mappings={
                    "interruption_recovery_minutes": 5,
                    "notification_sensitivity": 0.4,
                },
                follow_up="Resilient focus. You recover quickly."
            ),
            Choice(
                text="Depends what it is. Some things are worth breaking focus.",
                trait_mappings={
                    "interruption_recovery_minutes": 15,
                    "notification_sensitivity": 0.6,
                },
                follow_up="Selective attention. I'll learn what's worth the interrupt."
            ),
        ]
    ),

    # ─────────────────────────────────────────────────────────────────────────────
    # SCENARIO 8: Closing Scenario
    # ─────────────────────────────────────────────────────────────────────────────
    Scenario(
        id="otto_role",
        category=TraitCategory.PROTECTION_PREFERENCE,
        ascii_art="""
    ┌─────────────────────────────────────────┐
    │                                         │
    │              ╭──────────╮               │
    │              │  ○    ○  │               │
    │              │    \\/    │               │
    │              │   ────   │               │
    │              ╰──────────╯               │
    │                 OTTO                    │
    │                                         │
    └─────────────────────────────────────────┘
        """,
        setup="We're almost done.",
        otto_says="How should I think about my role with you?",
        choices=[
            Choice(
                text="A guardian. Protect me from myself when I can't.",
                trait_mappings={
                    "otto_role": "guardian",
                    "intervention_style": "proactive",
                },
                follow_up="Guardian role accepted. I'll watch out for you."
            ),
            Choice(
                text="A tool. Be useful, but stay out of the way.",
                trait_mappings={
                    "otto_role": "tool",
                    "intervention_style": "minimal",
                },
                follow_up="Tool mode. I'll be here when you call."
            ),
            Choice(
                text="A companion. Someone who gets how I work.",
                trait_mappings={
                    "otto_role": "companion",
                    "intervention_style": "adaptive",
                },
                follow_up="Companion mode. We'll figure this out together."
            ),
        ]
    ),
]


def get_scenarios() -> list[Scenario]:
    """Return all intake scenarios"""
    return SCENARIOS.copy()


def get_scenario_by_id(scenario_id: str) -> Scenario | None:
    """Get a specific scenario by ID"""
    for scenario in SCENARIOS:
        if scenario.id == scenario_id:
            return scenario
    return None
