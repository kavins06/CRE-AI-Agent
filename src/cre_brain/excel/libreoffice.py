"""Isolated-profile UNO worker for trusted synthetic .xlsx inputs only.

Native Office parsing is not an untrusted-workbook sandbox. Production invocation
must be inside the future owner-provided contained execution boundary.
"""

import os
import shutil
import signal
import subprocess
import tempfile
import uuid
from pathlib import Path

from openpyxl import load_workbook
from pydantic import Field

from cre_brain.config.settings import GateSettings
from cre_brain.domain.models import DomainModel
from cre_brain.excel.validation import formula_signature, validate_workbook


class LibreOfficeConfig(DomainModel):
    soffice: Path
    python: Path
    library_paths: tuple[Path, ...] = ()
    uno_paths: tuple[Path, ...] = ()
    ure_more_types: tuple[Path, ...] = ()
    timeout_s: int = Field(strict=True, ge=1, le=60, default=60)

    @classmethod
    def from_environment(cls) -> "LibreOfficeConfig":
        def paths(key: str) -> tuple[Path, ...]:
            return tuple(Path(p) for p in os.environ.get(key, "").split(os.pathsep) if p)

        office = os.environ.get("CRE_EXCEL_SOFFICE") or shutil.which("soffice")
        python = os.environ.get("CRE_EXCEL_UNO_PYTHON") or shutil.which(
            "python3", path="/usr/bin:/bin"
        )
        if not office or not python:
            raise ValueError(
                "Install the approved LibreOffice/UNO runtime or set "
                "CRE_EXCEL_SOFFICE and CRE_EXCEL_UNO_PYTHON"
            )
        return cls(
            soffice=Path(office),
            python=Path(python),
            library_paths=paths("CRE_EXCEL_LIBRARY_PATHS"),
            uno_paths=paths("CRE_EXCEL_UNO_PATHS"),
            ure_more_types=paths("CRE_EXCEL_URE_TYPES"),
            timeout_s=int(os.environ.get("CRE_EXCEL_TIMEOUT_S", "60")),
        )


class LibreOfficeEngine:
    def __init__(self, config: LibreOfficeConfig, *, gates: GateSettings) -> None:
        self.config = LibreOfficeConfig.model_validate(config.model_dump())
        self.gates = gates

    @classmethod
    def from_environment(cls, *, gates: GateSettings) -> "LibreOfficeEngine":
        return cls(LibreOfficeConfig.from_environment(), gates=gates)

    def recalc(self, path: Path) -> Path:
        original_formulas = validate_workbook(path, gates=self.gates)
        if not original_formulas:
            raise ValueError("Workbook has no formulas to recalculate")
        for executable in (self.config.soffice, self.config.python):
            if not executable.is_file():
                raise ValueError(f"Configured runtime executable is missing: {executable.name}")
        output = path.with_name(f"{path.stem}.recalculated-{uuid.uuid4().hex}.xlsx")
        with tempfile.TemporaryDirectory(prefix="cre-excel-") as directory:
            run = Path(directory)
            for name in ("home", "tmp", "profile"):
                (run / name).mkdir(mode=0o700)
            source = run / "input.xlsx"
            target = run / "output.xlsx"
            shutil.copyfile(path, source)
            environment = {
                "PATH": "/usr/bin:/bin",
                "HOME": str(run / "home"),
                "TMPDIR": str(run / "tmp"),
                "DBUS_SESSION_BUS_ADDRESS": "/dev/null",
                "LANG": "C.UTF-8",
                "LD_LIBRARY_PATH": os.pathsep.join(
                    str(p.resolve()) for p in self.config.library_paths
                ),
                "PYTHONPATH": os.pathsep.join(str(p.resolve()) for p in self.config.uno_paths),
                "URE_MORE_TYPES": " ".join(
                    p.resolve().as_uri() for p in self.config.ure_more_types
                ),
            }
            if not self.config.ure_more_types:
                environment.pop("URE_MORE_TYPES")
            if not self.config.uno_paths:
                environment.pop("PYTHONPATH")
            helper = Path(__file__).with_name("_uno_worker.py")
            try:
                process = subprocess.Popen(
                    [
                        str(self.config.python),
                        str(helper),
                        str(self.config.soffice.resolve()),
                        str(run),
                        str(source),
                        str(target),
                    ],
                    env=environment,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=os.name == "posix",
                )
            except Exception:
                raise RuntimeError("LibreOffice UNO recalculation failed") from None
            try:
                try:
                    process.communicate(timeout=self.config.timeout_s)
                except subprocess.TimeoutExpired:
                    raise RuntimeError("LibreOffice UNO recalculation timed out") from None
                finally:
                    # Reap gracefully first, then sweep this session's group even
                    # if the helper/Office launcher already exited. The session
                    # was created above; never discover or signal other groups.
                    try:
                        if process.returncode is None:
                            process.terminate()
                            try:
                                process.communicate(timeout=10)
                            except subprocess.TimeoutExpired:
                                pass
                    finally:
                        owned_group = getattr(process, "pid", None)
                        if os.name == "posix" and owned_group is not None:
                            try:
                                os.killpg(owned_group, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                        elif process.returncode is None:
                            process.kill()
                        if process.returncode is None:
                            process.communicate(timeout=5)
            except RuntimeError as exc:
                if str(exc) == "LibreOffice UNO recalculation timed out":
                    raise RuntimeError("LibreOffice UNO recalculation timed out") from None
                raise RuntimeError("LibreOffice UNO recalculation failed") from None
            except Exception:
                raise RuntimeError("LibreOffice UNO recalculation failed") from None
            if process.returncode != 0 or not target.is_file():
                raise RuntimeError("LibreOffice UNO recalculation failed") from None
            try:
                saved_formulas = validate_workbook(target, gates=self.gates)
            except Exception:
                raise RuntimeError("LibreOffice UNO output validation failed") from None
            for address, original in original_formulas.items():
                saved = saved_formulas.get(address)
                if saved is None or formula_signature(saved) != formula_signature(original):
                    raise RuntimeError("LibreOffice UNO recalculation changed a formula") from None
            try:
                cached = load_workbook(target, data_only=True)
                try:
                    for address in original_formulas:
                        sheet, cell = address.rsplit("!", 1)
                        if cached[sheet][cell].value is None:
                            raise RuntimeError(
                                "LibreOffice UNO missing recalculated cache"
                            ) from None
                finally:
                    cached.close()
            except RuntimeError:
                raise RuntimeError("LibreOffice UNO missing recalculated cache") from None
            except Exception:
                raise RuntimeError("LibreOffice UNO output validation failed") from None
            shutil.copyfile(target, output)
        return output
