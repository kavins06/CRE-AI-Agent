from __future__ import annotations

import io
import json
import re
import sys

EXCLUDED = re.compile(
    r"copyright|all rights reserved|©|NCMEC|missing (?:and exploited )?children|"
    r"reprinted (?:with|by) permission|courtesy of",
    re.IGNORECASE,
)


def main() -> None:
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 35))
    from pypdf import PdfReader, __version__

    if __version__ != "6.19.0":
        raise ValueError("Use the security-reviewed pypdf 6.19.0 optional documents extra")
    data = sys.stdin.buffer.read(25_000_001)
    if len(data) > 25_000_000 or not data.startswith(b"%PDF-"):
        raise ValueError("Invalid or oversized PDF")
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted or not 0 < len(reader.pages) <= 1000:
        raise ValueError("Encrypted or unbounded PDF")
    pages = []
    skipped = []
    total = 0
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        if len(text) > 80_000:
            raise ValueError("Page text exceeds extraction limit")
        total += len(text)
        if total > 3_000_000:
            raise ValueError("Document text exceeds extraction limit")
        if EXCLUDED.search(text) or not text.strip():
            skipped.append(number)
            continue
        pages.append({"page": number, "text": text})
    if not pages:
        raise ValueError("No reusable extractable text; OCR is not enabled")
    print(
        json.dumps(
            {
                "pages": pages,
                "skipped_pages": skipped,
                "page_count": len(reader.pages),
                "parser_version": "pypdf-6.19.0/text-v1",
            }
        )
    )


if __name__ == "__main__":
    main()
