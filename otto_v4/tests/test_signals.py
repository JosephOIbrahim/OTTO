"""Tests for PRISM signal detection (Phase 2.1)."""

from __future__ import annotations

import pytest

from otto.signals import (
    Signal,
    SignalType,
    detect_action_signals,
    detect_cognitive_signals,
    detect_signals,
)


class TestSignalDataclass:
    def test_valid_signal(self):
        s = Signal(type=SignalType.FRUSTRATED, confidence=0.8, evidence="caps")
        assert s.type == SignalType.FRUSTRATED
        assert s.confidence == 0.8

    def test_confidence_too_high(self):
        with pytest.raises(ValueError, match="0.0-1.0"):
            Signal(type=SignalType.FRUSTRATED, confidence=1.5)

    def test_confidence_too_low(self):
        with pytest.raises(ValueError, match="0.0-1.0"):
            Signal(type=SignalType.FRUSTRATED, confidence=-0.1)

    def test_boundary_confidence_zero(self):
        s = Signal(type=SignalType.FOCUSED, confidence=0.0)
        assert s.confidence == 0.0

    def test_boundary_confidence_one(self):
        s = Signal(type=SignalType.FOCUSED, confidence=1.0)
        assert s.confidence == 1.0

    def test_frozen(self):
        s = Signal(type=SignalType.STUCK, confidence=0.7)
        with pytest.raises(AttributeError):
            s.confidence = 0.9  # type: ignore[misc]


class TestSignalType:
    def test_action_signals_exist(self):
        assert SignalType.COMMITMENT_DETECTED.value == "commitment_detected"
        assert SignalType.ACTION_REQUIRED.value == "action_required"
        assert SignalType.MEETING_PROPOSED.value == "meeting_proposed"
        assert SignalType.DEADLINE_MENTIONED.value == "deadline_mentioned"

    def test_cognitive_signals_exist(self):
        assert SignalType.FRUSTRATED.value == "frustrated"
        assert SignalType.OVERWHELMED.value == "overwhelmed"
        assert SignalType.DEPLETED.value == "depleted"
        assert SignalType.STUCK.value == "stuck"
        assert SignalType.EXPLORING.value == "exploring"
        assert SignalType.FOCUSED.value == "focused"

    def test_alert_signals_exist(self):
        assert SignalType.BURST_DETECTED.value == "burst_detected"
        assert SignalType.CRASH_ZONE.value == "crash_zone"
        assert SignalType.SPIRAL.value == "spiral"
        assert SignalType.NUDGE_FATIGUE.value == "nudge_fatigue"


class TestFrustratedDetection:
    def test_caps_detected(self):
        signals = detect_signals("THIS IS NOT WORKING")
        types = {s.type for s in signals}
        assert SignalType.FRUSTRATED in types

    def test_repeated_punctuation(self):
        signals = detect_signals("why does this keep happening???")
        types = {s.type for s in signals}
        assert SignalType.FRUSTRATED in types

    def test_frustration_keywords(self):
        signals = detect_signals("ugh I hate this bug")
        types = {s.type for s in signals}
        assert SignalType.FRUSTRATED in types

    def test_defeat_language(self):
        signals = detect_signals("I can't figure this out, giving up")
        types = {s.type for s in signals}
        assert SignalType.FRUSTRATED in types

    def test_broken_statement(self):
        signals = detect_signals("this doesn't work at all")
        types = {s.type for s in signals}
        assert SignalType.FRUSTRATED in types


class TestOverwhelmedDetection:
    def test_too_much(self):
        signals = detect_signals("there's too much to do")
        types = {s.type for s in signals}
        assert SignalType.OVERWHELMED in types

    def test_no_starting_point(self):
        signals = detect_signals("I don't know where to start")
        types = {s.type for s in signals}
        assert SignalType.OVERWHELMED in types

    def test_everything_at_once(self):
        signals = detect_signals("I need to do everything at once")
        types = {s.type for s in signals}
        assert SignalType.OVERWHELMED in types

    def test_overwhelm_metaphor(self):
        signals = detect_signals("I'm drowning in work")
        types = {s.type for s in signals}
        assert SignalType.OVERWHELMED in types


class TestDepletedDetection:
    def test_fatigue_keyword(self):
        signals = detect_signals("I'm so tired today")
        types = {s.type for s in signals}
        assert SignalType.DEPLETED in types

    def test_cognitive_fatigue(self):
        signals = detect_signals("I can't think straight anymore")
        types = {s.type for s in signals}
        assert SignalType.DEPLETED in types

    def test_energy_keyword(self):
        signals = detect_signals("running on empty right now")
        types = {s.type for s in signals}
        assert SignalType.DEPLETED in types

    def test_short_message_heuristic(self):
        signals = detect_signals("ok")
        types = {s.type for s in signals}
        assert SignalType.DEPLETED in types

    def test_short_message_not_if_focused(self):
        # "next" triggers FOCUSED, so short-message heuristic should NOT add DEPLETED
        signals = detect_signals("next")
        types = {s.type for s in signals}
        assert SignalType.FOCUSED in types
        assert SignalType.DEPLETED not in types


class TestStuckDetection:
    def test_stuck_keyword(self):
        signals = detect_signals("I'm stuck on this problem")
        types = {s.type for s in signals}
        assert SignalType.STUCK in types

    def test_confusion(self):
        signals = detect_signals("I don't understand what to do")
        types = {s.type for s in signals}
        assert SignalType.STUCK in types

    def test_seeking_direction(self):
        signals = detect_signals("what should I do next?")
        types = {s.type for s in signals}
        assert SignalType.STUCK in types


class TestExploringDetection:
    def test_what_if(self):
        signals = detect_signals("what if we tried a different approach?")
        types = {s.type for s in signals}
        assert SignalType.EXPLORING in types

    def test_wondering(self):
        signals = detect_signals("I wonder if there's a better way")
        types = {s.type for s in signals}
        assert SignalType.EXPLORING in types

    def test_possibility(self):
        signals = detect_signals("could we use a graph database instead?")
        types = {s.type for s in signals}
        assert SignalType.EXPLORING in types

    def test_exploration_verb(self):
        signals = detect_signals("let's brainstorm some ideas")
        types = {s.type for s in signals}
        assert SignalType.EXPLORING in types


class TestFocusedDetection:
    def test_action_directive(self):
        signals = detect_signals("let's do it")
        types = {s.type for s in signals}
        assert SignalType.FOCUSED in types

    def test_completion_directive(self):
        signals = detect_signals("mark the report done")
        types = {s.type for s in signals}
        assert SignalType.FOCUSED in types

    def test_proceed(self):
        signals = detect_signals("proceed with the implementation")
        types = {s.type for s in signals}
        assert SignalType.FOCUSED in types


class TestDeadlineDetection:
    def test_day_of_week(self):
        signals = detect_signals("I need this done by Friday")
        types = {s.type for s in signals}
        assert SignalType.DEADLINE_MENTIONED in types

    def test_relative_deadline(self):
        signals = detect_signals("finish this by tomorrow")
        types = {s.type for s in signals}
        assert SignalType.DEADLINE_MENTIONED in types

    def test_iso_date(self):
        signals = detect_signals("deadline is 2026-03-15")
        types = {s.type for s in signals}
        assert SignalType.DEADLINE_MENTIONED in types

    def test_due_keyword(self):
        signals = detect_signals("the report is due by next week")
        types = {s.type for s in signals}
        assert SignalType.DEADLINE_MENTIONED in types


class TestMeetingDetection:
    def test_meeting_keyword(self):
        signals = detect_signals("let's schedule a meeting")
        types = {s.type for s in signals}
        assert SignalType.MEETING_PROPOSED in types

    def test_time_mention(self):
        signals = detect_signals("can we talk at 3pm?")
        types = {s.type for s in signals}
        assert SignalType.MEETING_PROPOSED in types


class TestCommitmentDetection:
    def test_i_will(self):
        signals = detect_signals("I will send the report tomorrow")
        types = {s.type for s in signals}
        assert SignalType.COMMITMENT_DETECTED in types

    def test_i_ll(self):
        signals = detect_signals("I'll call the dentist")
        types = {s.type for s in signals}
        assert SignalType.COMMITMENT_DETECTED in types

    def test_promise(self):
        signals = detect_signals("I promise to finish this today")
        types = {s.type for s in signals}
        assert SignalType.COMMITMENT_DETECTED in types

    def test_remind_request(self):
        signals = detect_signals("remind me to pick up groceries")
        types = {s.type for s in signals}
        assert SignalType.COMMITMENT_DETECTED in types


class TestMultipleSignals:
    def test_frustrated_and_stuck(self):
        signals = detect_signals("UGH I'm stuck and can't figure this out!!!")
        types = {s.type for s in signals}
        assert SignalType.FRUSTRATED in types
        assert SignalType.STUCK in types

    def test_commitment_with_deadline(self):
        signals = detect_signals("I'll finish the report by Friday")
        types = {s.type for s in signals}
        assert SignalType.COMMITMENT_DETECTED in types
        assert SignalType.DEADLINE_MENTIONED in types

    def test_overwhelmed_and_depleted(self):
        signals = detect_signals("I'm exhausted and there's too much to do")
        types = {s.type for s in signals}
        assert SignalType.DEPLETED in types
        assert SignalType.OVERWHELMED in types


class TestDeterminism:
    def test_same_input_same_output(self):
        """Same message must always produce identical signal list."""
        msg = "UGH I can't do this anymore, too much going on!!!"
        baseline = detect_signals(msg)
        for _ in range(50):
            result = detect_signals(msg)
            assert result == baseline

    def test_sorted_by_confidence_then_type(self):
        signals = detect_signals("I'll finish the report by Friday and schedule a meeting")
        for i in range(len(signals) - 1):
            a, b = signals[i], signals[i + 1]
            # Higher confidence first, or same confidence with name asc
            assert (a.confidence > b.confidence) or (
                a.confidence == b.confidence and a.type.name <= b.type.name
            )


class TestEdgeCases:
    def test_empty_string(self):
        assert detect_signals("") == []

    def test_whitespace_only(self):
        assert detect_signals("   ") == []

    def test_no_signals(self):
        signals = detect_signals("The weather is nice today")
        assert signals == []

    def test_threshold_filtering(self):
        # "help" has confidence 0.5, should be included at default threshold
        signals = detect_signals("help", threshold=0.5)
        types = {s.type for s in signals}
        assert SignalType.STUCK in types

    def test_high_threshold_filters_weak(self):
        # "help" confidence is 0.5, shouldn't pass 0.6 threshold
        signals = detect_signals("help", threshold=0.6)
        stuck = [s for s in signals if s.type == SignalType.STUCK]
        assert len(stuck) == 0

    def test_threshold_zero_returns_all(self):
        signals = detect_signals("help", threshold=0.0)
        assert len(signals) > 0


class TestConvenienceWrappers:
    def test_detect_action_signals(self):
        signals = detect_action_signals("I'll send the report by Friday and schedule a meeting")
        types = {s.type for s in signals}
        assert SignalType.COMMITMENT_DETECTED in types
        assert SignalType.DEADLINE_MENTIONED in types
        # No cognitive signals in action-only filter
        assert SignalType.FRUSTRATED not in types
        assert SignalType.DEPLETED not in types

    def test_detect_cognitive_signals(self):
        signals = detect_cognitive_signals("I'm stuck and frustrated, ugh!!!")
        types = {s.type for s in signals}
        assert SignalType.FRUSTRATED in types
        assert SignalType.STUCK in types
        # No action signals in cognitive-only filter
        assert SignalType.COMMITMENT_DETECTED not in types

    def test_action_signals_empty_on_cognitive_input(self):
        signals = detect_action_signals("I'm so tired")
        assert signals == []

    def test_cognitive_signals_empty_on_action_input(self):
        signals = detect_cognitive_signals("I'll call Sarah by Friday")
        assert signals == []
