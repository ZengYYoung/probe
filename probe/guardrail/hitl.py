"""HITL 状态机（纯函数，确定性，无 LLM/IO）。

SPEC §3.x Human-In-The-Loop 状态迁移：
- State: idle → proposing → awaiting_approval → executing → verifying → done / rejected
- 非法迁移抛 ValueError，由上层捕获处理。
"""

from __future__ import annotations

from enum import Enum


class State(str, Enum):
    idle = "idle"
    proposing = "proposing"
    awaiting_approval = "awaiting_approval"
    executing = "executing"
    verifying = "verifying"
    blocked = "blocked"
    done = "done"
    rejected = "rejected"


class Event(str, Enum):
    ActionProposed = "ActionProposed"
    NeedsApproval = "NeedsApproval"
    ApprovalGranted = "ApprovalGranted"
    ApprovalDenied = "ApprovalDenied"
    Executed = "Executed"
    Validated = "Validated"


_TABLE: dict[tuple[State, Event], State] = {
    (State.idle, Event.ActionProposed): State.proposing,
    (State.proposing, Event.NeedsApproval): State.awaiting_approval,
    # 无需审批的直通
    (State.proposing, Event.ApprovalGranted): State.executing,
    (State.awaiting_approval, Event.ApprovalGranted): State.executing,
    (State.awaiting_approval, Event.ApprovalDenied): State.rejected,
    (State.executing, Event.Executed): State.verifying,
    (State.verifying, Event.Validated): State.done,
}


def transition(state: State, event: Event) -> State:
    """纯函数状态迁移；非法组合抛 ValueError。"""
    nxt = _TABLE.get((state, event))
    if nxt is None:
        raise ValueError(f"illegal transition: {state} + {event}")
    return nxt
