import pytest
from probe.guardrail.hitl import State, Event, transition


def test_approve_flow():
    s = transition(State.idle, Event.ActionProposed); assert s == State.proposing
    s = transition(s, Event.NeedsApproval); assert s == State.awaiting_approval
    s = transition(s, Event.ApprovalGranted); assert s == State.executing
    s = transition(s, Event.Executed); assert s == State.verifying
    s = transition(s, Event.Validated); assert s == State.done


def test_deny():
    s = transition(State.awaiting_approval, Event.ApprovalDenied)
    assert s == State.rejected


def test_illegal_transition_raises():
    with pytest.raises(ValueError):
        transition(State.done, Event.ActionProposed)


def test_proposing_direct_to_executing_without_approval_raises():
    with pytest.raises(ValueError):
        transition(State.proposing, Event.Executed)
