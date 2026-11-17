"""Known-failure baselines: key normalization, snapshot, compare, growth, and the plane baseline CLI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from aircraft_platform.baseline import compare, growth, normalize_message, result_key, snapshot
from aircraft_platform.cli import cli
from aircraft_platform.design import FAIL, PASS, SKIP, WARN, CheckResult, Scorecard, TierReport
from aircraft_platform.design import DESIGNS_DIR


def card(*results: CheckResult, design_id: str = "d", max_tier: int = 5) -> Scorecard:
    return Scorecard(design_id, [TierReport(2, "physics", list(results))], max_tier)


def res(check_id: str, status: str, message: str) -> CheckResult:
    return CheckResult(check_id, status, message)


def snap(*results: CheckResult) -> dict:
    return snapshot(card(*results))


# --- key normalization -------------------------------------------------------

@pytest.mark.parametrize("check_id, message, expected", [
    ("wng-006-l", "wng-006-l: 3 N", "wng-006-l|wng-006-l: # N"),
    ("E-WNG-20", "E-WNG-20 peak 2.2 N <= 1.4 N", "E-WNG-20|E-WNG-20 peak # N <= # N"),
    ("T2.sim_rest", "at rest after 2.0 s", "T2.sim_rest|at rest after # s"),
    ("mec-003", "mec-003-l clips wing", "mec-003|mec-003-l clips wing"),
])
def test_ids_keep_their_digits(check_id, message, expected):
    assert result_key(check_id, message) == expected


def test_standalone_numbers_become_hash():
    assert normalize_message("peak 2.2 N <= 1.4 N") == "peak # N <= # N"
    assert normalize_message("pose down (-21 deg): 4 pairs") == "pose down (# deg): # pairs"


def test_percent_and_degree_signs():
    assert normalize_message("16.4% MAC") == "#% MAC"
    assert normalize_message("16.4 % MAC") == "#% MAC"
    assert normalize_message("pose up (21°)") == "pose up (#°)"


def test_same_numbers_different_values_share_a_key():
    assert result_key("T2.joint_load", "motor-l: 3.2 N <= 3 N") == result_key("T2.joint_load", "motor-l: 4.1 N <= 3 N")


# --- snapshot ----------------------------------------------------------------

def test_snapshot_keeps_only_fail_and_skip():
    s = snap(res("a", PASS, "ok 1"), res("b", WARN, "warn 2"), res("c", FAIL, "bad 3"), res("d", SKIP, "skip 4"))
    assert [e["check_id"] for e in s["known"]] == ["c", "d"]
    assert s["schema"] == 1 and s["design_id"] == "d" and s["accepted"] is False


def test_snapshot_dedupes_keeping_worse_status_and_counts():
    s = snap(res("x", SKIP, "gap 1 mm"), res("x", FAIL, "gap 2 mm"), res("x", SKIP, "gap 3 mm"))
    assert s["known"] == [{"key": "x|gap # mm", "status": FAIL, "check_id": "x",
                           "example": "gap 2 mm", "count": 3}]


def test_snapshot_single_entry_has_no_count():
    s = snap(res("x", FAIL, "bad 1"))
    assert "count" not in s["known"][0]


def test_accepted_snapshot_is_empty():
    s = snapshot(card(res("a", PASS, "ok"), res("b", WARN, "meh")))
    assert s["accepted"] is True and s["known"] == []


# --- compare -----------------------------------------------------------------

def test_no_baseline_and_not_accepted_is_missing_and_regression():
    c = compare(snap(res("x", FAIL, "bad 1")), None)
    assert c["missing_baseline"] is True
    assert [r["check_id"] for r in c["regressions"]] == ["x"]


def test_no_baseline_and_accepted_is_fine():
    c = compare(snapshot(card(res("a", PASS, "ok"))), None)
    assert c["missing_baseline"] is False and c["regressions"] == [] and c["improvements"] == []


def test_unchanged_known_result_counts_as_unchanged():
    base = snap(res("x", FAIL, "bad 1"))
    c = compare(snap(res("x", FAIL, "bad 9")), base)
    assert c == {"regressions": [], "improvements": [], "unchanged_count": 1, "missing_baseline": False}


def test_new_key_is_regression():
    base = snap(res("x", FAIL, "bad 1"))
    c = compare(snap(res("x", FAIL, "bad 1"), res("y", FAIL, "new 2")), base)
    assert [r["check_id"] for r in c["regressions"]] == ["y"]


def test_fail_where_baseline_had_skip_is_regression():
    c = compare(snap(res("x", FAIL, "bad 1")), snap(res("x", SKIP, "bad 1")))
    assert [r["status"] for r in c["regressions"]] == [FAIL]


def test_skip_where_baseline_had_fail_is_improvement():
    c = compare(snap(res("x", SKIP, "bad 1")), snap(res("x", FAIL, "bad 1")))
    assert c["regressions"] == []
    assert [r["reason"] for r in c["improvements"]] == ["FAIL now SKIP"]


def test_key_gone_is_improvement():
    c = compare(snap(), snap(res("x", FAIL, "bad 1")))
    assert c["regressions"] == []
    assert [(r["check_id"], r["reason"]) for r in c["improvements"]] == [("x", "no longer present")]


def test_count_rise_is_regression_and_fall_is_improvement():
    base = snap(res("x", FAIL, "a 1"), res("x", FAIL, "a 2"))
    more = compare(snap(res("x", FAIL, "a 1"), res("x", FAIL, "a 2"), res("x", FAIL, "a 3")), base)
    assert [r["reason"] for r in more["regressions"]] == ["count rose from 2 to 3"]
    fewer = compare(snap(res("x", FAIL, "a 1")), base)
    assert fewer["regressions"] == []
    assert [r["reason"] for r in fewer["improvements"]] == ["count fell from 2 to 1"]


def test_growth_lists_new_keys():
    old = snap(res("x", FAIL, "bad 1"))
    new = snap(res("x", FAIL, "bad 1"), res("y", SKIP, "gap 2"))
    assert [(e["key"], e["reason"]) for e in growth(old, new)] == [(result_key("y", "gap 2"), "added")]
    assert [e["key"] for e in growth(None, new)] == sorted(result_key(e, m) for e, m in [("x", "bad 1"), ("y", "gap 2")])
    assert growth(new, old) == []


def test_growth_flags_count_bump_and_skip_to_fail():
    old = snap(res("x", FAIL, "a 1"), res("z", SKIP, "gap 1"))
    new = snap(res("x", FAIL, "a 1"), res("x", FAIL, "a 2"), res("z", FAIL, "gap 1"))
    reasons = {e["check_id"]: e["reason"] for e in growth(old, new)}
    assert reasons == {"x": "count 1\u21922", "z": "SKIP\u2192FAIL"}


# --- identity beyond the message (A1, A1b, A2b, A1c) --------------------------

def test_regression_plus_count_bump_in_same_change_is_growth():
    base = snap(res("T2.joint_load", FAIL, "4: 3.2 N at 4.5g exceeds rating 2 N", ))
    head = snap(res("T2.joint_load", FAIL, "4: 3.2 N at 4.5g exceeds rating 2 N"),
                res("T2.joint_load", FAIL, "4: 3.2 N at 4.5g exceeds rating 2 N"))
    assert [r["reason"] for r in compare(head, base)["regressions"]] == ["count rose from 1 to 2"]
    assert [e["reason"] for e in growth(base, head)] == ["count 1\u21922"]


def test_static_margin_crossing_band_is_regression_not_improvement():
    above = snap(res("T3.static_margin", FAIL, "15.3% MAC (target 5%-15%)", ) )
    above = snapshot(card(CheckResult("T3.static_margin", FAIL, "15.3% MAC (target 5%-15%)", "", {"band": "above"})))
    below = snapshot(card(CheckResult("T3.static_margin", FAIL, "3.8% MAC (target 5%-15%)", "", {"band": "below"})))
    c = compare(below, above)
    assert [r["check_id"] for r in c["regressions"]] == ["T3.static_margin"]


def test_swapped_numeric_subject_at_same_message_is_regression():
    base = snapshot(card(CheckResult("T2.joint_load", FAIL, "#: # N at 4.5g exceeds rating # N", "", {"joint": "4"})))
    head = snapshot(card(CheckResult("T2.joint_load", FAIL, "#: # N at 4.5g exceeds rating # N", "", {"joint": "5"})))
    c = compare(head, base)
    assert [r["reason"] for r in c["regressions"]] == ["not in baseline"]


def test_truncated_list_gaining_an_id_past_truncation_is_regression():
    base = snapshot(card(CheckResult("T1.kinematic_link", SKIP, "7 pairs: a, b, c, d, e, f, \u2026", "",
                                     {"pairs": ["a & b", "c & d", "e & f", "g & h", "i & j", "k & l", "m & n"]})))
    head = snapshot(card(CheckResult("T1.kinematic_link", SKIP, "8 pairs: a, b, c, d, e, f, \u2026", "",
                                     {"pairs": ["a & b", "c & d", "e & f", "g & h", "i & j", "k & l", "m & n", "o & p"]})))
    assert compare(head, base)["regressions"], "a new pair past the truncation must be a regression"


def test_numbers_and_non_string_data_are_not_in_the_key():
    assert result_key("T", "x", {"volume_mm3": 3.2, "nested": {"a": "b"}}) == "T|x"
    assert result_key("T", "x", {"band": "above"}) == 'T|x|{"band":"above"}'


def test_rename_matches_gone_folder_with_identical_keys(tmp_path):
    from aircraft_platform.cli import _renamed_from
    cur = snap(res("x", FAIL, "bad 1"))
    assert _renamed_from("brand-new-folder", cur, {"gone-folder-xyz": cur}) == "gone-folder-xyz"
    assert _renamed_from("brand-new-folder", cur, {"gone-folder-xyz": snap(res("y", FAIL, "bad 2"))}) is None
    assert _renamed_from("brand-new-folder", snap(), {"gone-folder-xyz": snap()}) is None


# --- CLI ---------------------------------------------------------------------

def _copy_example(tmp_path: Path) -> Path:
    folder = tmp_path / "example-tailsitter-wing"
    folder.mkdir()
    (folder / "plane.yaml").write_text((DESIGNS_DIR / "example-tailsitter-wing" / "plane.yaml").read_text())
    return folder


def _set_rating(folder: Path, joint: str, rated_load_n: float) -> None:
    data = yaml.safe_load((folder / "plane.yaml").read_text())
    for att in data["attachments"]:
        if att["id"] == joint:
            att["rated_load_n"] = rated_load_n
            break
    else:
        raise KeyError(joint)
    (folder / "plane.yaml").write_text(yaml.safe_dump(data, sort_keys=False))


def test_check_accepted_example_without_baseline_exits_0(example):
    assert not (example.parent / "baseline.json").exists()
    result = CliRunner().invoke(cli, ["baseline", "check", str(example.parent)])
    assert result.exit_code == 0, result.output
    assert "Accepted" in result.output


def test_update_then_check_then_regression_names_joint(tmp_path):
    folder = _copy_example(tmp_path)
    runner = CliRunner()

    # Force a FAIL on motor-l: its drop-test and static loads exceed a 3 N rating.
    _set_rating(folder, "motor-l", 3)
    assert runner.invoke(cli, ["baseline", "update", str(folder)]).exit_code == 0
    assert (folder / "baseline.json").is_file()
    check = runner.invoke(cli, ["baseline", "check", str(folder)])
    assert check.exit_code == 0, check.output

    # Now a second joint fails: a new key, so a regression.
    _set_rating(folder, "mount-l", 2)
    check = runner.invoke(cli, ["baseline", "check", str(folder), "--format", "md"])
    assert check.exit_code == 1, check.output
    regressions_part = check.output.split("### Improvements")[0]
    assert "### Regressions" in regressions_part
    assert "mount-l" in regressions_part
    assert "motor-l" not in regressions_part


def test_update_on_accepted_design_deletes_stale_baseline(tmp_path):
    folder = _copy_example(tmp_path)
    (folder / "baseline.json").write_text("{}\n")
    result = CliRunner().invoke(cli, ["baseline", "update", str(folder)])
    assert result.exit_code == 0, result.output
    assert not (folder / "baseline.json").exists()
    assert "deleted" in result.output


def test_check_md_table_shows_message_and_reason(tmp_path):
    folder = _copy_example(tmp_path)
    runner = CliRunner()
    _set_rating(folder, "motor-l", 3)
    assert runner.invoke(cli, ["baseline", "update", str(folder)]).exit_code == 0
    _set_rating(folder, "mount-l", 2)
    out = runner.invoke(cli, ["baseline", "check", str(folder)]).output
    assert "| check_id | status | message | reason |" in out
    assert "| T2.joint_load | FAIL | mount-l: 3.6 N at 4.5g exceeds rating 2 N | not in baseline |" in out
