"""DBF import per concept: the CONCEPTS table, the design id plumbing and the CLI checks. No CAD build runs here
(the full concept A import takes minutes and is checked by diffing designs/concept-a against a fresh import)."""
from __future__ import annotations

import pytest
from click.testing import CliRunner

from aircraft_platform.cli import cli
from aircraft_platform.importers import dbf
from aircraft_platform.importers.dbf import CONCEPTS, default_design_id, import_concept
from aircraft_platform.importers.dbf_ratings import rating

REQUIRED_KEYS = {
    "title", "name", "description", "inspired_by", "frame_note", "morphology", "paths", "root_part", "type_overrides",
    "kinematic_link_children", "mass_proxy_reasons", "manufacturing", "manufacturing_prefix", "planform", "propulsion",
    "notes", "ratings",
}
RATINGS_KEYS = {
    "structures_dir", "doc", "peel_not_sourced", "peel_text", "strap_text", "no_capacity_text", "bond_tau_mpa", "bond_tau_src",
    "xps_shear_kpa", "xps_src", "steel_tension_mpa", "steel_tension_src", "steel_shear_mpa", "steel_shear_src",
    "stress_area_mm2",
}


def test_concept_a_has_every_required_key():
    a = CONCEPTS["A"]
    assert REQUIRED_KEYS <= set(a), sorted(REQUIRED_KEYS - set(a))
    assert RATINGS_KEYS <= set(a["ratings"]), sorted(RATINGS_KEYS - set(a["ratings"]))
    assert a["root_part"] == "WNG-001"
    assert set(a["paths"]) >= {"cad", "parts_csv", "params", "glb", "parts_src"}


def test_concept_a_ratings_table_is_complete():
    doc = CONCEPTS["A"]["ratings"]["doc"]
    assert "E-FIN-01" in doc and doc["E-FIN-01"][0] == "k"
    assert "E-WNG-01" in doc and doc["E-WNG-01"][0] == "abs"


def test_default_design_id_is_concept_letter_lowercase():
    assert default_design_id("A") == "concept-a"
    assert default_design_id("b") == "concept-b"


def test_unknown_concept_is_a_clear_error(tmp_path):
    with pytest.raises(ValueError, match="unknown concept 'Z'.*known concepts: A"):
        import_concept(tmp_path, concept="Z", out_dir=tmp_path / "o")


def test_invalid_design_id_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="invalid design id"):
        import_concept(tmp_path, concept="A", design_id="Bad Id", out_dir=tmp_path / "o")


def test_cli_unknown_concept_lists_known_concepts(tmp_path):
    res = CliRunner().invoke(cli, ["import", "dbf", "--dbf-root", str(tmp_path), "--concept", "Q"])
    assert res.exit_code == 2
    assert "unknown concept 'Q'" in res.output and "A" in res.output


def test_cli_invalid_id_is_an_error(tmp_path):
    res = CliRunner().invoke(cli, ["import", "dbf", "--dbf-root", str(tmp_path), "--id", "Not OK"])
    assert res.exit_code == 2
    assert "invalid id" in res.output


def test_rating_uses_the_passed_concept_table_not_a_global():
    """A table with no doc rows must not pick up concept A's rating for the same edge id."""
    empty = dict(CONCEPTS["A"]["ratings"], doc={})
    val, kind, _ = rating({"id": "E-FIN-01", "via": "CT-EPOXY"}, {}, {}, None, empty)
    assert kind == "placeholder" and val is None
    val_a, kind_a, _ = rating({"id": "E-FIN-01", "via": "CT-EPOXY"}, {}, {}, None)
    assert kind_a == "doc"


def test_part_type_override_applies_to_the_root_part():
    assert dbf.part_type("WNG-001", "core", CONCEPTS["A"]["type_overrides"]) == "wing"
    assert dbf.part_type("WNG-001", "core") == "other"
