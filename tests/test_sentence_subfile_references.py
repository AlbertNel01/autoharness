"""Punctuation must not turn a usable carried script into a missing path."""
import subprocess

import pytest

from autoharness.hook import promoter
from autoharness.lib import sidecar, skill_store
from autoharness.stage_skill import server

BODY = "---\nname: run\ndescription: Use when formatting a date as ISO.\n---\n# Run\nRun {pointer}\n"
SCRIPT = "printf 'ok\\n'\n"


@pytest.mark.parametrize("pointer", ["scripts/run.sh.", "./scripts/run.sh.", "scripts/run.sh...", "`scripts/run.sh`."])
def test_sentence_reference_lands_and_script_remains_usable(tmp_path, pointer):
    roots = {"project": tmp_path, "global": tmp_path / "unused"}
    staged = server.stage({
        "action": "create", "name": "run", "body": BODY.format(pointer=pointer),
        "files": {"scripts/run.sh": SCRIPT}, "reason": "supported script reference",
        "evidence": "local fixture",
    }, run_id="sentence", root=tmp_path)
    assert staged["ok"]
    verdicts = promoter.drain("sentence", roots=roots)
    assert verdicts[0]["ok"], verdicts
    script = skill_store.skill_path("project", "run", tmp_path).parent / "scripts/run.sh"
    result = subprocess.run(["/bin/sh", str(script)], capture_output=True, text=True,
                            encoding="utf-8", timeout=5, check=True)
    assert result.stdout == "ok\n"


def test_a_real_legacy_trailing_period_filename_remains_referenced(tmp_path):
    roots = {"project": tmp_path, "global": tmp_path / "unused"}
    skill_store.write_body("project", "run", BODY.format(pointer="`scripts/run.sh.`"), tmp_path)
    sidecar.create("project", "run", 0, tmp_path)
    directory = skill_store.skill_path("project", "run", tmp_path).parent / "scripts"
    directory.mkdir()
    (directory / "run.sh.").write_text(SCRIPT, encoding="utf-8")
    verdict = promoter.promote({
        "action": "update", "name": "run", "body": BODY.format(pointer="scripts/run.sh."),
        "reason": "retain an existing supported filename", "evidence": "local fixture",
    }, roots=roots)
    assert verdict["ok"], verdict
    assert not (directory / "run.sh").exists()


def test_longer_unknown_pointer_does_not_match_the_carried_prefix(tmp_path):
    roots = {"project": tmp_path, "global": tmp_path / "unused"}
    staged = server.stage({
        "action": "create", "name": "run", "body": BODY.format(pointer="scripts/run.sh.bak."),
        "files": {"scripts/run.sh": SCRIPT}, "reason": "negative control", "evidence": "local fixture",
    }, run_id="unknown", root=tmp_path)
    assert staged["ok"]  # stage cannot yet probe a live skill directory
    verdicts = promoter.drain("unknown", roots=roots)
    assert not verdicts[0]["ok"]
    assert any(kind == "structure" for kind, _ in verdicts[0]["findings"])
    assert not skill_store.skill_path("project", "run", tmp_path).exists()


@pytest.mark.parametrize("pointer", ["`scripts/run.sh.`", "``scripts/run.sh.``", "`Run scripts/run.sh. now`"])
def test_a_period_inside_a_code_span_denotes_the_actual_filename(tmp_path, pointer):
    roots = {"project": tmp_path, "global": tmp_path / "unused"}
    staged = server.stage({
        "action": "create", "name": "run", "body": BODY.format(pointer=pointer),
        "files": {"scripts/run.sh": SCRIPT}, "reason": "explicit filename negative control",
        "evidence": "local fixture",
    }, run_id="literal", root=tmp_path)
    assert staged["ok"]
    verdicts = promoter.drain("literal", roots=roots)
    assert not verdicts[0]["ok"]
    assert any("scripts/run.sh." in text for kind, text in verdicts[0]["findings"] if kind == "structure")
    assert not skill_store.skill_path("project", "run", tmp_path).exists()
