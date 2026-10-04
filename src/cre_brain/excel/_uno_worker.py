"""Private standalone UNO client, executed by a UNO-capable configured Python.

No repository imports: the runtime Python need not have cre_brain installed.
"""

import importlib
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any


def _property(factory: Any, name: str, value: object) -> Any:
    result = factory()
    result.Name = name
    result.Value = value
    return result


def _interrupted(signum: int, frame: object) -> None:
    raise RuntimeError("UNO worker interrupted")


def _main() -> None:
    office, directory, source, target = map(Path, sys.argv[1:])
    pipe = "cre" + uuid.uuid4().hex
    # The client needs UNO bootstrap paths; office must not inherit those.
    environment = {
        key: os.environ[key]
        for key in ("PATH", "HOME", "TMPDIR", "DBUS_SESSION_BUS_ADDRESS", "LANG", "LD_LIBRARY_PATH")
        if key in os.environ
    }
    signal.signal(signal.SIGTERM, _interrupted)
    signal.signal(signal.SIGINT, _interrupted)
    process = None
    reader = None
    document = None
    try:
        process = subprocess.Popen(
            [
                str(office),
                f"-env:UserInstallation={(directory / 'profile').as_uri()}",
                "--headless",
                "--nodefault",
                "--nologo",
                "--norestore",
                f"--accept=pipe,name={pipe};urp;StarOffice.ComponentContext",
            ],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        tail = bytearray()

        def drain() -> None:
            assert process.stderr is not None
            while chunk := process.stderr.read(1024):
                tail.extend(chunk)
                del tail[:-2000]

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        uno = importlib.import_module("uno")

        def factory() -> Any:
            return uno.createUnoStruct("com.sun.star.beans.PropertyValue")

        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local
        )
        deadline = time.monotonic() + 15
        while True:
            if process.poll() is not None:
                raise RuntimeError(
                    f"Office exited before UNO connection (exit {process.returncode})"
                )
            try:
                context = resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError("UNO connection timeout") from None
                time.sleep(0.1)
        desktop = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", context
        )
        document = desktop.loadComponentFromURL(
            source.as_uri(),
            "_blank",
            0,
            tuple(
                _property(factory, name, value)
                for name, value in (
                    ("Hidden", True),
                    ("UpdateDocMode", 0),
                    (
                        "MacroExecutionMode",
                        uno.getConstantByName("com.sun.star.document.MacroExecMode.NEVER_EXECUTE"),
                    ),
                    ("ReadOnly", False),
                )
            ),
        )
        if document is None:
            raise RuntimeError("UNO could not open the workbook")
        document.enableAutomaticCalculation(True)
        document.calculateAll()
        document.storeAsURL(
            target.as_uri(),
            tuple(
                _property(factory, name, value)
                for name, value in (("FilterName", "Calc MS Excel 2007 XML"), ("Overwrite", True))
            ),
        )
        document.close(True)
        document = None
        desktop.terminate()
        process.wait(timeout=5)
    finally:
        # Do not call a possibly blocked UNO bridge during timeout cleanup.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if reader is not None:
            reader.join(timeout=1)
        # The bounded native tail is private and discarded, never forwarded.


def main() -> None:
    try:
        _main()
    except Exception:
        raise RuntimeError("UNO worker failed") from None


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stderr.write("UNO worker failed\n")
        sys.exit(1)
