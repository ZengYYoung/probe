from probe.core.types import Status


def test_status_enums():
    assert Status.SUCCESS == "SUCCESS"
    assert Status.BLOCKED_NO_PROGRESS == "BLOCKED_NO_PROGRESS"
    assert {
        Status.SUCCESS,
        Status.STOPPED_BUDGET,
        Status.BLOCKED_NO_PROGRESS,
        Status.STOPPED_REJECTED,
        Status.ERROR,
    }
