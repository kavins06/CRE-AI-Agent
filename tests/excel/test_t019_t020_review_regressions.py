import io
import signal
import subprocess
import sys
from types import SimpleNamespace

import pytest
from test_recalc import stale_workbook

from cre_brain.config import load
from cre_brain.excel import _uno_worker
from cre_brain.excel.libreoffice import LibreOfficeConfig, LibreOfficeEngine


def test_t020_ac1_uno_worker_disables_macro_execution(monkeypatch, tmp_path):
    observed = {}

    class Office:
        returncode = None
        stderr = io.BytesIO()

        def poll(self):
            return self.returncode

        def wait(self, timeout):
            self.returncode = 0

    office = Office()

    class Document:
        def enableAutomaticCalculation(self, enabled):
            assert enabled

        def calculateAll(self):
            pass

        def storeAsURL(self, url, properties):
            pass

        def close(self, deliver_ownership):
            pass

    class Desktop:
        def loadComponentFromURL(self, url, frame, flags, properties):
            observed.update((p.Name, p.Value) for p in properties)
            return Document()

        def terminate(self):
            office.returncode = 0

    class ServiceManager:
        def createInstanceWithContext(self, name, context):
            if name.endswith("UnoUrlResolver"):
                return SimpleNamespace(resolve=lambda endpoint: context)
            assert name.endswith("Desktop")
            return Desktop()

    context = SimpleNamespace(ServiceManager=ServiceManager())

    def constant(name):
        assert name == "com.sun.star.document.MacroExecMode.NEVER_EXECUTE"
        return 0

    uno = SimpleNamespace(
        getComponentContext=lambda: context,
        createUnoStruct=lambda name: SimpleNamespace(),
        getConstantByName=constant,
    )
    monkeypatch.setattr(_uno_worker.importlib, "import_module", lambda name: uno)
    monkeypatch.setattr(_uno_worker.subprocess, "Popen", lambda *args, **kwargs: office)
    monkeypatch.setattr(_uno_worker.signal, "signal", lambda *args: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker",
            "/usr/bin/soffice",
            str(tmp_path),
            str(tmp_path / "in.xlsx"),
            str(tmp_path / "out.xlsx"),
        ],
    )
    _uno_worker.main()
    assert observed["MacroExecutionMode"] == 0


def test_t020_ac1_force_cleanup_stops_owned_office_descendants(monkeypatch, tmp_path):
    source = tmp_path / "source.xlsx"
    stale_workbook(source)
    observed = {}
    groups = []

    class BlockedWorker:
        pid = 123456789
        returncode = None

        def __init__(self, args, **kwargs):
            observed.update(kwargs)

        def communicate(self, timeout):
            if groups:
                self.returncode = -signal.SIGKILL
                return None, b""
            raise subprocess.TimeoutExpired("worker", timeout)

        def terminate(self):
            pass

        def kill(self):
            self.returncode = -signal.SIGKILL

    monkeypatch.setattr(subprocess, "Popen", BlockedWorker)
    monkeypatch.setattr("os.killpg", lambda process_group, sig: groups.append((process_group, sig)))
    engine = LibreOfficeEngine(
        LibreOfficeConfig(soffice="/usr/bin/python3", python="/usr/bin/python3", timeout_s=1),
        gates=load().gates,
    )
    with pytest.raises(RuntimeError, match="timed out"):
        engine.recalc(source)
    assert observed["start_new_session"] is True
    assert groups == [(BlockedWorker.pid, signal.SIGKILL)]
