from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.rag.canonical import sha256_bytes
from scripts.rag.run_yaml_cpp_mechanics import (
    EVALUATION_PLAN_FILE,
    FIXTURE_FILE,
    PLAN_MANIFEST_FILE,
    FrozenInputs,
    MechanicsError,
    RepositoryState,
    SourceReplacementTransaction,
    build_evaluation_plan,
    build_fixture_class_span,
    ensure_execution_not_attempted,
    load_config,
    raw_offsets_for_normalized_range,
    run_plan_only,
    validate_fixture_class_span,
    verify_baseline,
    verify_frozen_selection_and_direct_tests,
    verify_target_source,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs/rag/pilot/yaml_cpp_yaml_node_mechanics_v1.json"
YAML_CPP_ROOT = (ROOT / ".." / "cpp-rag-pilot-yaml-cpp").resolve()


def _real_frozen(config: dict[str, object]) -> FrozenInputs:
    raw, raw_hash, normalized_hash, target_source = verify_target_source(
        config, YAML_CPP_ROOT
    )
    fixture_source = build_fixture_class_span(config, target_source)
    return FrozenInputs(
        original_source_bytes=raw,
        original_source_sha256=raw_hash,
        normalized_source_sha256=normalized_hash,
        target_source=target_source,
        target_source_sha256=sha256_bytes(target_source.encode("utf-8")),
        fixture_source=fixture_source,
        fixture_source_sha256=sha256_bytes(fixture_source.encode("utf-8")),
        selection_sha256=config["frozen_selection"]["sha256"],
        baseline_report_sha256=config["evaluation"]["baseline_report_sha256"],
        project_state=RepositoryState(
            head="a" * 40,
            branch="agent/rag-protocol-v0-9",
            clean=True,
        ),
        pilot_state=RepositoryState(head="b" * 40, branch=None, clean=True),
    )


class FrozenFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)
        _raw, _raw_hash, _normalized_hash, self.target_source = verify_target_source(
            self.config, YAML_CPP_ROOT
        )

    def test_fixture_is_deterministic_and_matches_frozen_hash(self) -> None:
        first = build_fixture_class_span(self.config, self.target_source)
        second = build_fixture_class_span(self.config, self.target_source)
        self.assertEqual(first, second)
        self.assertEqual(
            sha256_bytes(first.encode("utf-8")),
            "27f2f2aa671c0e8834e9b7b9819b09b1988975afcdc142da8b5ce9371b82190c",
        )

    def test_fixture_diff_is_exactly_one_fixed_comment(self) -> None:
        fixture = build_fixture_class_span(self.config, self.target_source)
        comment = self.config["fixture"]["comment"]
        anchor = self.config["fixture"]["insertion_anchor"]
        self.assertNotEqual(fixture, self.target_source)
        self.assertEqual(fixture.count(comment), 1)
        self.assertEqual(fixture.replace(comment, "", 1), self.target_source)
        self.assertIn(anchor + comment, fixture)

    def test_fixture_and_original_are_complete_structurally_valid_spans(self) -> None:
        fixture = build_fixture_class_span(self.config, self.target_source)
        validate_fixture_class_span(self.config, self.target_source, fixture)
        self.assertTrue(fixture.startswith("class YAML_CPP_API Node"))
        self.assertTrue(fixture.rstrip().endswith("}"))
        self.assertFalse(fixture.rstrip().endswith("};"))

    def test_fixture_hash_check_rejects_changed_comment(self) -> None:
        fixture = build_fixture_class_span(self.config, self.target_source)
        changed = fixture.replace("pipeline validation", "changed validation", 1)
        with self.assertRaisesRegex(MechanicsError, "fixed comment|material"):
            validate_fixture_class_span(self.config, self.target_source, changed)

    def test_target_source_hash_checks_reject_changed_raw_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            pilot_root = Path(raw_directory)
            source_path = pilot_root / self.config["target"]["path"]
            source_path.parent.mkdir(parents=True)
            original = (
                YAML_CPP_ROOT / self.config["target"]["path"]
            ).read_bytes()
            source_path.write_bytes(original + b" ")
            with self.assertRaisesRegex(MechanicsError, "raw SHA-256 mismatch"):
                verify_target_source(self.config, pilot_root)


class FrozenEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)

    def test_selection_direct_tests_and_baseline_are_frozen(self) -> None:
        self.assertEqual(
            verify_frozen_selection_and_direct_tests(
                self.config, ROOT, YAML_CPP_ROOT
            ),
            self.config["frozen_selection"]["sha256"],
        )
        self.assertEqual(
            verify_baseline(self.config, ROOT),
            self.config["evaluation"]["baseline_report_sha256"],
        )

    def test_evaluation_plan_contains_all_mechanics_stages_and_zero_calls(self) -> None:
        plan = build_evaluation_plan(self.config)
        self.assertEqual(plan["ordered_stages"], self.config["required_stage_records"])
        self.assertEqual(
            [stage["stage"] for stage in plan["stages"]],
            self.config["required_stage_records"],
        )
        self.assertFalse(plan["zero_generation_policy"]["llm_allowed"])
        self.assertEqual(plan["zero_generation_policy"]["llm_call_count"], 0)
        self.assertFalse(
            plan["zero_generation_policy"]["generation_server_contact_allowed"]
        )


class ReplacementAndRestorationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)

    def test_normalized_range_maps_to_only_the_crlf_target_bytes(self) -> None:
        raw = b"prefix\r\nTARGET\r\nsuffix\r\n"
        normalized = raw.replace(b"\r\n", b"\n")
        start = normalized.index(b"TARGET")
        end = start + len(b"TARGET")
        raw_start, raw_end = raw_offsets_for_normalized_range(raw, start, end)
        self.assertEqual(raw[raw_start:raw_end], b"TARGET")
        replaced = raw[:raw_start] + b"FIXTURE" + raw[raw_end:]
        self.assertEqual(replaced[:raw_start], raw[:raw_start])
        self.assertEqual(replaced[raw_start + len(b"FIXTURE") :], raw[raw_end:])

    def test_source_transaction_restores_exact_raw_bytes_after_failure(self) -> None:
        original = b"prefix\r\nTARGET\r\nsuffix\r\n"
        normalized = original.replace(b"\r\n", b"\n")
        start = normalized.index(b"TARGET")
        end = start + len(b"TARGET")
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "node.h"
            path.write_bytes(original)
            transaction = SourceReplacementTransaction(
                source_path=path,
                original_bytes=original,
                start=start,
                end=end,
                replacement_bytes=b"FIXTURE",
                expected_original_sha256=sha256_bytes(original),
            )
            with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                with transaction:
                    self.assertIn(b"FIXTURE", path.read_bytes())
                    raise RuntimeError("simulated failure")
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(transaction.replaced)
            self.assertTrue(transaction.restored)
            self.assertEqual(transaction.restored_sha256, sha256_bytes(original))


class PlanAndOneShotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)
        self.frozen = _real_frozen(self.config)

    def _temporary_config(self, temporary: Path) -> dict[str, object]:
        config = copy.deepcopy(self.config)
        config["output_path"] = temporary.relative_to(ROOT).as_posix()
        return config

    def test_attempt_failure_or_result_marker_blocks_execution(self) -> None:
        policy = self.config["one_shot_policy"]
        with tempfile.TemporaryDirectory() as raw:
            run_root = Path(raw)
            for field in ("attempt_marker", "failure_marker", "result_marker"):
                marker = run_root / policy[field]
                with self.subTest(field=field):
                    marker.write_text("{}\n", encoding="utf-8")
                    with self.assertRaisesRegex(
                        MechanicsError, "already attempted, failed, or complete"
                    ):
                        ensure_execution_not_attempted(self.config, run_root)
                    marker.unlink()

    def test_plan_only_writes_exactly_three_artifacts_and_makes_zero_mutations(self) -> None:
        source_path = YAML_CPP_ROOT / self.config["target"]["path"]
        source_before = source_path.read_bytes()
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            temporary = Path(raw)
            config = self._temporary_config(temporary)
            with (
                mock.patch(
                    "scripts.rag.run_yaml_cpp_mechanics.validate_frozen_inputs",
                    return_value=self.frozen,
                ),
                mock.patch(
                    "scripts.rag.run_yaml_cpp_mechanics._verify_docker_image"
                ) as docker_inspect,
                mock.patch(
                    "scripts.rag.run_yaml_cpp_mechanics.subprocess.run"
                ) as process,
            ):
                manifest = run_plan_only(config, CONFIG_PATH, ROOT, YAML_CPP_ROOT)
            docker_inspect.assert_not_called()
            process.assert_not_called()
            plan_root = temporary / "plan"
            self.assertEqual(
                {path.name for path in plan_root.iterdir()},
                {FIXTURE_FILE, EVALUATION_PLAN_FILE, PLAN_MANIFEST_FILE},
            )
            saved = json.loads(
                (plan_root / PLAN_MANIFEST_FILE).read_text(encoding="utf-8")
            )
            for record in (manifest, saved):
                self.assertFalse(record["llm_called"])
                self.assertEqual(record["llm_call_count"], 0)
                self.assertFalse(record["generation_server_contacted"])
                self.assertFalse(record["source_replaced"])
                self.assertFalse(record["docker_called"])
                self.assertFalse(record["configure_started"])
                self.assertFalse(record["build_started"])
                self.assertFalse(record["tests_started"])
            self.assertEqual(source_path.read_bytes(), source_before)


if __name__ == "__main__":
    unittest.main()
