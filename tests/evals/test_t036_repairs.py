"""Additive review regressions; no existing or generated truth is inspected here."""

import hashlib
import importlib
import os
import stat
from decimal import ROUND_UP, DefaultContext, Inexact, getcontext, setcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.main import get_command

from cre_brain.cli import create_app, discover_plugins


def generator():
    from cre_brain.evals.commands import load_generator

    return load_generator()


def test_t036_ac3_generator_rejects_substituted_package_stage(tmp_path):
    paths = importlib.import_module(generator().__name__ + ".paths")
    destination = paths.Destination(tmp_path / "p")
    target = tmp_path / "scoring"
    target.mkdir()
    try:
        stage = destination.stage()
        stage.rename(stage.with_name("displaced"))
        stage.symlink_to(target, target_is_directory=True)
        with pytest.raises(ValueError, match="identity|stage"):
            destination.publish()
        assert not (tmp_path / "p").exists()
    finally:
        destination.close(success=False)


def test_t036_ac3_generator_pins_private_source_namespace(tmp_path, monkeypatch):
    paths = importlib.import_module(generator().__name__ + ".paths")
    destination = paths.Destination(tmp_path / "p")
    original = paths._rename_new
    checked = []

    def check_directories(parent, source, target):
        source_fd, destination_fd = parent
        assert source_fd != destination_fd
        assert stat.S_IMODE(os.fstat(source_fd).st_mode) == 0o700
        checked.append(True)
        original(parent, source, target)

    monkeypatch.setattr(paths, "_rename_new", check_directories)
    try:
        destination.stage()
        destination.publish()
        assert checked
    finally:
        destination.close(success=False)


def test_t036_ac3_generator_parent_substitution_keeps_pinned_stage(tmp_path):
    paths = importlib.import_module(generator().__name__ + ".paths")
    destination = paths.Destination(tmp_path / "p")
    try:
        stage = destination.stage()
        (stage / "owned.txt").write_bytes(b"owned")
        job = next(tmp_path.glob(".cre-gen-*"))
        job.rename(tmp_path / "displaced")
        job.mkdir()
        (job / "owned.txt").write_bytes(b"replacement")
        destination.publish()
        assert (tmp_path / "p/owned.txt").read_bytes() == b"owned"
        assert (job / "owned.txt").read_bytes() == b"replacement"
    finally:
        destination.close(success=True)


def test_t036_ac3_generator_rollback_preserves_swapped_directory(tmp_path, monkeypatch):
    paths = importlib.import_module(generator().__name__ + ".paths")
    destination = paths.Destination(tmp_path / "t")
    destination.stage()
    destination.publish()
    original_stat, original_lstat = os.stat, os.lstat
    swapped = []

    def after_check(result, name):
        if Path(name).name == "t" and not swapped:
            (tmp_path / "t").rename(tmp_path / "owned-displaced")
            (tmp_path / "t").mkdir()
            (tmp_path / "t/sentinel").write_bytes(b"another writer")
            swapped.append(True)
        return result

    def race_stat(name, *args, **kwargs):
        return after_check(original_stat(name, *args, **kwargs), name)

    def race_lstat(name, *args, **kwargs):
        return after_check(original_lstat(name, *args, **kwargs), name)

    monkeypatch.setattr(os, "stat", race_stat)
    monkeypatch.setattr(os, "lstat", race_lstat)
    destination.close(success=False)
    assert swapped
    assert (tmp_path / "t/sentinel").read_bytes() == b"another writer"


def test_t036_ac2_generator_temp_collision_preserves_existing_file(tmp_path, monkeypatch):
    paths = importlib.import_module(generator().__name__ + ".paths")
    monkeypatch.setattr(paths, "uuid4", lambda: SimpleNamespace(hex="fixed"))
    sentinel = tmp_path / ".cre-gen-document-fixed"
    sentinel.write_bytes(b"another writer")
    with pytest.raises(FileExistsError):
        paths.write_document(tmp_path / "om.pdf", b"document")
    assert sentinel.read_bytes() == b"another writer"
    assert not (tmp_path / "om.pdf").exists()


def context_state(context):
    return (
        context.prec,
        context.rounding,
        context.Emin,
        context.Emax,
        context.capitals,
        context.clamp,
        dict(context.flags),
        dict(context.traps),
    )


@pytest.mark.parametrize("mutation", ["rounding", "traps", "limits"])
def test_t036_ac1_generator_ignores_mutated_default_decimal_context(mutation):
    gen = generator()

    def fingerprint():
        deal = gen.sample_deal("review-context")
        digest = hashlib.sha256(deal.model_dump_json().encode())
        digest.update(gen.render.rent_roll_bytes(deal, layout="yardi", extension="xlsx"))
        digest.update(gen.render.t12_bytes(deal))
        return digest.digest()

    baseline = fingerprint()
    saved_default, saved_active = DefaultContext.copy(), getcontext().copy()
    try:
        if mutation == "rounding":
            DefaultContext.rounding = ROUND_UP
        elif mutation == "traps":
            DefaultContext.traps[Inexact] = True
        else:
            DefaultContext.Emin, DefaultContext.Emax = -2, 2
            DefaultContext.clamp = 1
        getcontext().prec = 5
        getcontext().rounding = ROUND_UP
        before_default, before_active = context_state(DefaultContext), context_state(getcontext())
        actual = fingerprint()
        assert actual == baseline
        assert context_state(DefaultContext) == before_default
        assert context_state(getcontext()) == before_active
    finally:
        for field in ("prec", "rounding", "Emin", "Emax", "capitals", "clamp", "flags", "traps"):
            setattr(DefaultContext, field, getattr(saved_default, field))
        setcontext(saved_active)


def test_t036_ac3_generator_is_builtin_without_changing_plugin_discovery():
    assert list(discover_plugins()) == []
    assert "evals" in get_command(create_app()).commands
    assert "evals" not in get_command(create_app(plugins=[])).commands


@pytest.mark.parametrize("identifier", ["=1+1", "+1", "-1", "@SUM(A1)", "U01", "U0001", "U001\n"])
@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_t036_ac2_generator_formula_unit_id_rejected(identifier, extension):
    gen = generator()
    identity = importlib.import_module(gen.__name__ + ".identity").input_id
    deal = gen.sample_deal("review-unit-id")
    values = deal.units[0].model_dump(exclude={"input_id"})
    values["unit_id"] = identifier
    unit = deal.units[0].model_copy(
        update={
            "unit_id": identifier,
            "input_id": identity(f"{deal.deal_id}:unit:1", values),
        }
    )
    custom = deal.model_copy(update={"units": (unit, *deal.units[1:])})
    with pytest.raises(ValueError, match="unit_id"):
        gen.render.rent_roll_bytes(custom, layout="yardi", extension=extension)


def test_t036_ac2_generator_payload_fd_closed_when_identity_read_fails(tmp_path, monkeypatch):
    paths = importlib.import_module(generator().__name__ + ".paths")
    real_open, real_fstat, real_close = os.open, os.fstat, os.close
    captured = []

    def capture_open(name, flags, *args, **kwargs):
        descriptor = real_open(name, flags, *args, **kwargs)
        if name == "payload" and flags & os.O_CREAT:
            captured.append(descriptor)
        return descriptor

    def fail_payload_stat(descriptor):
        if descriptor in captured:
            raise OSError("injected payload identity failure")
        return real_fstat(descriptor)

    monkeypatch.setattr(paths.os, "open", capture_open)
    monkeypatch.setattr(paths.os, "fstat", fail_payload_stat)
    try:
        with pytest.raises(OSError, match="injected payload identity failure"):
            paths.write_document(tmp_path / "document.csv", b"synthetic")
        assert len(captured) == 1
        assert not (tmp_path / "document.csv").exists()
        with pytest.raises(OSError) as closed:
            real_fstat(captured[0])
        assert closed.value.errno == 9
    finally:
        for descriptor in captured:
            try:
                real_close(descriptor)
            except OSError:
                pass


def test_t036_ac3_generator_parent_closed_after_job_close_error(tmp_path, monkeypatch):
    paths = importlib.import_module(generator().__name__ + ".paths")
    destination = paths.Destination(tmp_path / "packages")
    destination.stage()
    job, parent = destination.job, destination.parent
    real_close = os.close

    def close_and_fail(descriptor):
        real_close(descriptor)
        if descriptor == job:
            raise OSError("injected job close failure")

    monkeypatch.setattr(paths.os, "close", close_and_fail)
    try:
        with pytest.raises(OSError, match="injected job close failure"):
            destination.close(success=False)
        with pytest.raises(OSError) as closed:
            os.fstat(parent)
        assert closed.value.errno == 9
    finally:
        try:
            real_close(parent)
        except OSError:
            pass


def test_t036_ac2_generator_fdopen_failure_preserves_error_and_closes_fd(tmp_path, monkeypatch):
    paths = importlib.import_module(generator().__name__ + ".paths")
    real_fdopen, real_fstat, real_close = os.fdopen, os.fstat, os.close
    captured = []

    def fail_after_acquisition(descriptor, *args, **kwargs):
        captured.append(descriptor)
        real_fdopen(descriptor, *args, **kwargs).close()
        raise MemoryError("injected stream construction failure")

    monkeypatch.setattr(paths.os, "fdopen", fail_after_acquisition)
    try:
        with pytest.raises(MemoryError, match="injected stream construction failure"):
            paths.write_document(tmp_path / "document.csv", b"synthetic")
        assert len(captured) == 1
        with pytest.raises(OSError) as closed:
            real_fstat(captured[0])
        assert closed.value.errno == 9
        assert list(tmp_path.iterdir()) == []
    finally:
        for descriptor in captured:
            try:
                real_close(descriptor)
            except OSError:
                pass
