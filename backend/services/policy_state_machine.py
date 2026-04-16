from fastapi import HTTPException

from models.policy import PolicyStatus

# Valid transitions: (current_status, action) -> new_status
ALLOWED_TRANSITIONS: dict[tuple[PolicyStatus, str], PolicyStatus] = {
    (PolicyStatus.BOUND, "issue"): PolicyStatus.ISSUED,
    (PolicyStatus.ISSUED, "endorse"): PolicyStatus.ISSUED,
    (PolicyStatus.ISSUED, "cancel"): PolicyStatus.CANCELLED,
    (PolicyStatus.CANCELLED, "reinstate"): PolicyStatus.ISSUED,
}

ACTION_LABELS = {
    "issue": "issued",
    "endorse": "endorsed",
    "cancel": "cancelled",
    "reinstate": "reinstated",
}


def validate_and_transition(policy, action: str) -> PolicyStatus:
    key = (policy.status, action)
    new_status = ALLOWED_TRANSITIONS.get(key)
    if new_status is None:
        label = ACTION_LABELS.get(action, action)
        raise HTTPException(
            status_code=422,
            detail=f"A {policy.status.value} policy cannot be {label}",
        )
    return new_status
