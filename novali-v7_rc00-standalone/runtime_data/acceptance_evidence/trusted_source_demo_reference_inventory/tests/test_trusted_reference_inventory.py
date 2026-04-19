from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "successor_shell"
    / "trusted_reference_inventory.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "trusted_reference_inventory_under_test",
        MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load trusted reference inventory module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TrustedReferenceInventoryTests(unittest.TestCase):
    def test_reports_required_roles_as_satisfied(self) -> None:
        module = _load_module()
        evidence_items = [
            {
                "role_id": role_id,
                "title": role_id,
                "source_id": "fixture_source",
                "absolute_path": f"/fixture/{role_id}",
                "relative_path": role_id,
                "present": True,
                "sha256": "fixture",
                "size_bytes": 1,
                "why_relevant": "fixture",
            }
            for role_id in module.REQUIRED_ROLES
        ]
        inventory = module.build_reference_inventory(
            capability_id="trusted_source_reference_inventory_capability_v1",
            workspace_root=Path.cwd(),
            evidence_items=evidence_items,
            knowledge_pack={"knowledge_pack_id": "fixture_pack"},
            request={"request_id": "fixture_request"},
            active_bounded_reference_target_id="candidate::bounded_reference",
        )
        self.assertTrue(inventory["required_roles_satisfied"])
        self.assertEqual(inventory["missing_role_ids"], [])

    def test_reports_missing_roles_when_evidence_is_incomplete(self) -> None:
        module = _load_module()
        inventory = module.build_reference_inventory(
            capability_id="trusted_source_reference_inventory_capability_v1",
            workspace_root=Path.cwd(),
            evidence_items=[],
            knowledge_pack={"knowledge_pack_id": "fixture_pack"},
            request={"request_id": "fixture_request"},
            active_bounded_reference_target_id="candidate::bounded_reference",
        )
        self.assertFalse(inventory["required_roles_satisfied"])
        self.assertEqual(set(inventory["missing_role_ids"]), set(module.REQUIRED_ROLES))


if __name__ == "__main__":
    unittest.main()
