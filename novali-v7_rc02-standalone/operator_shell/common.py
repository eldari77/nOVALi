from __future__ import annotations

import os

OPERATOR_CONTEXT_ENV = "NOVALI_OPERATOR_CONTEXT_ROLE"
OPERATOR_ROLE_OPERATOR = "operator"
OPERATOR_ROLE_RUNTIME = "runtime"
OPERATOR_SESSION_FILE_ENV = "NOVALI_OPERATOR_SESSION_FILE"
OPERATOR_POLICY_ROOT_ENV = "NOVALI_OPERATOR_POLICY_ROOT"
OPERATOR_RUNTIME_LOCK_ENV = "NOVALI_OPERATOR_RUNTIME_LOCK"
STARTUP_MODE_ENV = "NOVALI_STARTUP_MODE"
STARTUP_MODE_CANONICAL_OPERATOR = "canonical_operator"
STARTUP_MODE_DEVELOPER_DIRECT = "developer_direct_non_canonical"


def resolve_startup_mode() -> str:
    value = str(os.environ.get(STARTUP_MODE_ENV, "")).strip()
    return value or STARTUP_MODE_DEVELOPER_DIRECT


class OperatorConstraintViolationError(RuntimeError):
    def __init__(self, message: str, *, constraint_id: str = "", enforcement_class: str = "") -> None:
        self.constraint_id = str(constraint_id)
        self.enforcement_class = str(enforcement_class)
        super().__init__(message)


class OperatorPolicyMutationRefusedError(OperatorConstraintViolationError):
    pass
