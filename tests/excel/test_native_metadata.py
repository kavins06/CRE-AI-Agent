import xml.etree.ElementTree as ET
import zipfile

import openpyxl
import pytest

from cre_brain.config import load
from cre_brain.excel.validation import validate_workbook

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
LO = "http://schemas.libreoffice.org/"
URI = "{7626C862-2A13-11E5-B345-FEFF819CDC9F}"


def native_metadata(path, variant=None):
    workbook = openpyxl.Workbook()
    workbook.active["A1"] = "=SUM(B1:B2)"
    workbook.save(path)
    with zipfile.ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    name = "xl/workbook.xml"
    root = ET.fromstring(files[name])
    container = ET.SubElement(root, f"{{{NS}}}extLst")
    extension = ET.SubElement(container, f"{{{NS}}}ext", {"uri": URI})
    metadata = ET.SubElement(extension, f"{{{LO}}}extCalcPr", {"stringRefSyntax": "ExcelA1"})
    if variant == "uri":
        extension.set("uri", "unknown")
    elif variant == "syntax":
        metadata.set("stringRefSyntax", "CalcA1")
    elif variant == "attribute":
        metadata.set("executable", "true")
    elif variant == "child":
        ET.SubElement(metadata, f"{{{NS}}}f").text = "1/0"
    elif variant == "extra":
        ET.SubElement(container, f"{{{NS}}}ext", {"uri": "unknown"})
    elif variant == "container":
        root.append(ET.fromstring(ET.tostring(container)))
    elif variant == "location":
        root.remove(container)
        name = "xl/worksheets/sheet1.xml"
        root = ET.fromstring(files[name])
        root.append(container)
    files[name] = ET.tostring(root)
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def test_t020_ac1_allows_exact_native_excel_a1_metadata(tmp_path):
    path = tmp_path / "native.xlsx"
    native_metadata(path)
    assert validate_workbook(path, gates=load().gates) == {"Sheet!A1": "=SUM(B1:B2)"}


@pytest.mark.parametrize(
    "variant", ["uri", "syntax", "attribute", "child", "extra", "container", "location"]
)
def test_native_metadata_rejects_unproven_extensions(tmp_path, variant):
    path = tmp_path / "unsupported.xlsx"
    native_metadata(path, variant)
    with pytest.raises(ValueError, match="Unsupported workbook feature"):
        validate_workbook(path, gates=load().gates)
