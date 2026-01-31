"""
Orchestra Dogfooding Session Runner
===================================

Simulates a realistic coding session to demonstrate Orchestra's
cognitive state tracking and intervention capabilities.

This script:
1. Simulates user messages with various emotional/cognitive states
2. Tracks cognitive state changes through the session
3. Records interventions that were triggered
4. Exports the session to .usda for analysis
5. Generates a case study document

Usage:
    python session_runner.py
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# Add Orchestra to path
orchestra_path = Path(__file__).parent.parent / "src"
if str(orchestra_path) not in sys.path:
    sys.path.insert(0, str(orchestra_path))

from otto.cognitive_stage import create_cognitive_stage
from otto.prism_detector import create_detector
from otto.tension_surfacer import create_tension_surfacer
from otto.cognitive_support import CognitiveSupportManager
from otto.cognitive_state import BurnoutLevel, MomentumPhase


# =============================================================================
# Session Recording
# =============================================================================

@dataclass
class SessionExchange:
    """Record of a single exchange in the session."""
    exchange_num: int
    timestamp: str
    user_message: str

    # Detection results
    signals_detected: Dict[str, Any]
    priority_signal: tuple

    # State before processing
    state_before: Dict[str, Any]

    # State after processing
    state_after: Dict[str, Any]

    # Interventions
    intervention_triggered: bool = False
    intervention_type: Optional[str] = None
    intervention_message: Optional[str] = None

    # Tensions
    tensions_detected: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange_num": self.exchange_num,
            "timestamp": self.timestamp,
            "user_message": self.user_message,
            "signals": self.signals_detected,
            "priority_signal": {
                "category": self.priority_signal[0],
                "signal": self.priority_signal[1],
                "score": self.priority_signal[2],
            } if self.priority_signal else None,
            "state_before": self.state_before,
            "state_after": self.state_after,
            "intervention_triggered": self.intervention_triggered,
            "intervention_type": self.intervention_type,
            "intervention_message": self.intervention_message,
            "tensions": self.tensions_detected,
        }


@dataclass
class SessionRecord:
    """Complete record of a dogfooding session."""
    session_id: str
    start_time: str
    end_time: Optional[str] = None
    exchanges: List[SessionExchange] = field(default_factory=list)
    interventions_triggered: int = 0
    interventions_accepted: int = 0  # Simulated
    burnout_escalations: int = 0
    mode_switches: int = 0
    tensions_surfaced: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_exchanges": len(self.exchanges),
            "interventions_triggered": self.interventions_triggered,
            "interventions_accepted": self.interventions_accepted,
            "burnout_escalations": self.burnout_escalations,
            "mode_switches": self.mode_switches,
            "tensions_surfaced": self.tensions_surfaced,
            "exchanges": [e.to_dict() for e in self.exchanges],
        }


# =============================================================================
# Simulated Session Scenarios
# =============================================================================

# Realistic session progression: starts focused, hits obstacles, gets frustrated,
# Orchestra intervenes, user recovers
SESSION_SCENARIO = [
    # Phase 1: Focused start (exchanges 1-5)
    {
        "message": "I need to implement the user authentication module today",
        "expected_mode": "focused",
        "expected_burnout": "green",
    },
    {
        "message": "Let's start with the login endpoint",
        "expected_mode": "focused",
        "expected_burnout": "green",
    },
    {
        "message": "The basic structure is working, now adding password hashing",
        "expected_mode": "focused",
        "expected_burnout": "green",
    },
    {
        "message": "Good progress. Now let's add JWT token generation",
        "expected_mode": "focused",
        "expected_burnout": "green",
    },
    {
        "message": "Token generation done. Testing the flow now",
        "expected_mode": "focused",
        "expected_burnout": "green",
    },

    # Phase 2: Exploration (exchanges 6-8)
    {
        "message": "What if we added OAuth support? That might be useful",
        "expected_mode": "exploring",
        "expected_burnout": "green",
    },
    {
        "message": "Exploring different OAuth providers... Google, GitHub, maybe Discord?",
        "expected_mode": "exploring",
        "expected_burnout": "green",
    },
    {
        "message": "Actually let me focus back on the core auth first",
        "expected_mode": "focused",
        "expected_burnout": "green",
    },

    # Phase 3: Hitting obstacles (exchanges 9-14)
    {
        "message": "The tests are failing but I don't understand why",
        "expected_mode": "focused",
        "expected_burnout": "green",
    },
    {
        "message": "Still stuck on this test failure. Tried three different approaches",
        "expected_mode": "focused",
        "expected_burnout": "yellow",
        "note": "Stuck signal detected, burnout should start to rise",
    },
    {
        "message": "This is frustrating. The error message doesn't make sense",
        "expected_mode": "focused",
        "expected_burnout": "yellow",
        "note": "Frustration signal detected",
    },
    {
        "message": "I've been debugging this for an hour and nothing works",
        "expected_mode": "focused",
        "expected_burnout": "yellow",
    },
    {
        "message": "WHY ISN'T THIS WORKING?! I've tried everything",
        "expected_mode": "focused",
        "expected_burnout": "orange",
        "note": "CAPS + frustration = intervention point",
        "should_intervene": True,
    },
    {
        "message": "Fine, let me step back and look at this differently",
        "expected_mode": "focused",
        "expected_burnout": "orange",
        "note": "User self-correcting after intervention",
    },

    # Phase 4: Recovery attempt (exchanges 15-18)
    {
        "message": "OK I found the issue - it was a typo in the config",
        "expected_mode": "focused",
        "expected_burnout": "yellow",
        "note": "Success should help recover",
    },
    {
        "message": "Tests passing now. That was rough but we got through it",
        "expected_mode": "focused",
        "expected_burnout": "yellow",
    },
    {
        "message": "Let me document what I learned from that debugging session",
        "expected_mode": "teaching",
        "expected_burnout": "green",
        "note": "Mode switch to teaching for documentation",
    },
    {
        "message": "Documentation done. What's next on the list?",
        "expected_mode": "focused",
        "expected_burnout": "green",
    },

    # Phase 5: Fatigue setting in (exchanges 19-22)
    {
        "message": "I should probably add rate limiting next",
        "expected_mode": "focused",
        "expected_burnout": "green",
    },
    {
        "message": "getting tired... maybe one more thing",
        "expected_mode": "focused",
        "expected_burnout": "yellow",
        "note": "Energy depletion signals",
    },
    {
        "message": "I can't focus anymore. Everything is blurring together",
        "expected_mode": "recovery",
        "expected_burnout": "orange",
        "note": "Should trigger recovery suggestion",
        "should_intervene": True,
    },
    {
        "message": "You're right, I should take a break",
        "expected_mode": "recovery",
        "expected_burnout": "orange",
        "note": "User accepts intervention",
    },
]


# =============================================================================
# Session Runner
# =============================================================================

class DogfoodingSession:
    """Runs a simulated dogfooding session with Orchestra."""

    def __init__(self):
        self.stage = create_cognitive_stage()
        self.detector = create_detector()
        self.surfacer = create_tension_surfacer(self.stage)
        self.support = CognitiveSupportManager()

        self.record = SessionRecord(
            session_id=self.stage.checksum()[:8],
            start_time=datetime.now().isoformat(),
        )

        # Track previous burnout for escalation detection
        self._prev_burnout = "green"

    def run_exchange(self, exchange_num: int, user_message: str) -> SessionExchange:
        """Process a single exchange and record results."""

        # Capture state before
        state = self.stage.get_cognitive_state()
        state_before = {
            "burnout": state.burnout_level.value,
            "momentum": state.momentum_phase.value,
            "energy": state.energy_level.value,
            "mode": state.mode.value,
            "exchange_count": state.exchange_count,
        }

        # Detect signals
        signals = self.detector.detect(user_message)
        priority_signal = signals.get_priority_signal()

        # Check for safety intervention
        needs_intervention, reason = self.detector.quick_safety_check(user_message)

        # Detect tensions
        tension_report = self.surfacer.detect(signals, user_message)

        # Check cognitive constraints
        check = self.support.check(state, text=user_message)

        # Update state based on signals
        self._update_state(signals, user_message)

        # Capture state after
        state = self.stage.get_cognitive_state()
        state_after = {
            "burnout": state.burnout_level.value,
            "momentum": state.momentum_phase.value,
            "energy": state.energy_level.value,
            "mode": state.mode.value,
            "exchange_count": state.exchange_count,
        }

        # Track burnout escalation
        if (self._prev_burnout != state_after["burnout"] and
            self._burnout_level(state_after["burnout"]) > self._burnout_level(self._prev_burnout)):
            self.record.burnout_escalations += 1
        self._prev_burnout = state_after["burnout"]

        # Build exchange record
        exchange = SessionExchange(
            exchange_num=exchange_num,
            timestamp=datetime.now().isoformat(),
            user_message=user_message,
            signals_detected=signals.to_dict(),
            priority_signal=(
                priority_signal[0].name,
                priority_signal[1],
                priority_signal[2]
            ),
            state_before=state_before,
            state_after=state_after,
        )

        # Record intervention if triggered
        if needs_intervention or check.recovery_needed or check.body_check_needed:
            exchange.intervention_triggered = True
            exchange.intervention_type = reason or ("recovery" if check.recovery_needed else "body_check")
            exchange.intervention_message = self._get_intervention_message(reason, check)
            self.record.interventions_triggered += 1

        # Record tensions
        if tension_report.has_tensions():
            exchange.tensions_detected = [t.to_dict() for t in tension_report.tensions]
            self.record.tensions_surfaced += len(tension_report.tensions)

        return exchange

    def _update_state(self, signals, user_message: str):
        """Update cognitive state based on signals."""
        state = self.stage.get_cognitive_state()

        # Update from emotional signals
        if signals.emotional_score >= 0.7:
            state.escalate_burnout()
        elif signals.emotional_score >= 0.5:
            if state.burnout_level == BurnoutLevel.GREEN:
                state.burnout_level = BurnoutLevel.YELLOW

        # Update mode from signals
        if signals.mode_detected:
            prev_mode = state.mode.value
            self.stage.set_mode(signals.mode_detected)
            if prev_mode != signals.mode_detected:
                self.record.mode_switches += 1

        # Update energy from signals
        if signals.energy_state:
            self.stage.set_session_value("energy_level", signals.energy_state)

        # Increment exchange count
        state.increment_exchange(rapid=True)

        # Check for recovery conditions
        if "tired" in user_message.lower() or "exhausted" in user_message.lower():
            if state.energy_level.value != "depleted":
                self.stage.set_session_value("energy_level", "low")

        # Check for stuck patterns
        if "stuck" in user_message.lower() or "doesn't work" in user_message.lower():
            if state.burnout_level == BurnoutLevel.GREEN:
                state.burnout_level = BurnoutLevel.YELLOW

        # Save state
        self.stage.save()

    def _burnout_level(self, level: str) -> int:
        """Convert burnout level to numeric for comparison."""
        return {"green": 0, "yellow": 1, "orange": 2, "red": 3}.get(level, 0)

    def _get_intervention_message(self, reason: str, check) -> str:
        """Get intervention message based on trigger."""
        if reason == "caps_detected":
            return "I notice some frustration. Let's pause and make sure we're on the same page."
        elif reason and "overwhelmed" in reason:
            return "That sounds like a lot. Let's break this down into smaller pieces."
        elif check.recovery_needed:
            return "You're running on empty. What would help right now?"
        elif check.body_check_needed:
            return "Quick check: How are you doing? Water? Stretch?"
        return "Let's take a moment to check in."

    def run_scenario(self, scenario: List[Dict]) -> SessionRecord:
        """Run a complete session scenario."""
        print(f"Starting dogfooding session {self.record.session_id}")
        print("=" * 60)

        for i, step in enumerate(scenario, 1):
            message = step["message"]
            exchange = self.run_exchange(i, message)
            self.record.exchanges.append(exchange)

            # Print progress
            print(f"\n[Exchange {i}]")
            print(f"  User: {message[:60]}{'...' if len(message) > 60 else ''}")
            print(f"  Signal: {exchange.priority_signal[0]}:{exchange.priority_signal[1]} ({exchange.priority_signal[2]:.2f})")
            print(f"  Burnout: {exchange.state_before['burnout']} -> {exchange.state_after['burnout']}")

            if exchange.intervention_triggered:
                print(f"  [!] INTERVENTION: {exchange.intervention_type}")
                print(f"      \"{exchange.intervention_message}\"")

            if exchange.tensions_detected:
                print(f"  [T] Tensions: {len(exchange.tensions_detected)} detected")

            # Brief pause to make it feel like a real session
            time.sleep(0.1)

        self.record.end_time = datetime.now().isoformat()

        print("\n" + "=" * 60)
        print("Session complete!")
        print(f"  Total exchanges: {len(self.record.exchanges)}")
        print(f"  Interventions triggered: {self.record.interventions_triggered}")
        print(f"  Burnout escalations: {self.record.burnout_escalations}")
        print(f"  Mode switches: {self.record.mode_switches}")
        print(f"  Tensions surfaced: {self.record.tensions_surfaced}")

        return self.record

    def export_session(self) -> tuple:
        """Export session to files."""
        output_dir = Path(__file__).parent

        # Export .usda
        usda_path = self.stage.export(f"dogfood_{self.record.session_id}.usda")

        # Export session JSON
        json_path = output_dir / f"session_{self.record.session_id}.json"
        with open(json_path, 'w') as f:
            json.dump(self.record.to_dict(), f, indent=2)

        return usda_path, json_path


# =============================================================================
# Main
# =============================================================================

def main():
    """Run the dogfooding session."""
    session = DogfoodingSession()

    # Run the scenario
    record = session.run_scenario(SESSION_SCENARIO)

    # Export results
    usda_path, json_path = session.export_session()

    print(f"\nExported session:")
    print(f"  USD Stage: {usda_path}")
    print(f"  JSON Record: {json_path}")

    # Return paths for further processing
    return usda_path, json_path, record


if __name__ == "__main__":
    main()
