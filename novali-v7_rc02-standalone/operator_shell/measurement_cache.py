"""Cache only exact payloads from an explicit measurement dependency manifest."""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any, Mapping
from . import research_procedures as records, planner_resources
from .research_tools import digest

# Includes measurement and plan preflight semantics, excludes lesson authorship,
# feedback ingestion, transaction settlement and practice scheduling.
DEPENDENCIES = ("planner_resources.py", "research_runtime.py", "planner_authoring.py",
                "theory_runtime.py", "theory_workspace.py", "theory_methods.py",
                "research_semantics.py", "research_tools.py", "method_patches.py",
                "research_feedback.py", "method_repair.py", "executable_measurement.py")


def dependencies() -> dict[str, str]:
    return {name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in DEPENDENCIES}


def valid(row: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    return (row.get("input_sha256")==digest(context) and row.get("cache_dependencies")==dependencies()
            and row.get("measurements_sha256")==digest(row.get("measurements")))


def create(root: Path, context: Mapping[str, Any]) -> dict[str, Any]:
    measurements=planner_resources.measurement_catalog(context)
    return records.store(root,"planning_measurements",{
        "input_sha256":digest(context), "implementation":records.implementation(),
        "cache_dependencies":dependencies(), "measurements":measurements,
        "measurements_sha256":digest(measurements)})
