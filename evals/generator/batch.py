"""Stage complete public packages and scoring-only answers in separate fresh roots."""

import json
import os
import platform
import zlib
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

from ._context import isolated_decimal
from .models import DefaultPriors, LatentDeal
from .paths import Destination, validate_destinations
from .render import RENT_ROLL_COLUMNS, om_bytes, rent_roll_bytes, t12_bytes
from .sampler import sample_deal
from .truth import calculate_truth, input_manifest


def _json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n")


def render_om(deal: LatentDeal, path: Path) -> None:
    """Batch's private pinned staging directory; public renderer uses stricter paths."""
    with path.open("xb") as handle:
        handle.write(om_bytes(deal))


@isolated_decimal
def generate(
    *, n: int, seed: str, out_packages: Path, out_truth: Path, priors: DefaultPriors | None = None
) -> None:
    if type(n) is not int or not 1 <= n <= 1000:
        raise ValueError("Batch size must be an integer in [1, 1000]")
    priors = DefaultPriors.model_validate(priors or DefaultPriors())
    # Validate all inputs before staging, and never accept deal names from the caller.
    first = sample_deal(seed, index=1, priors=priors)
    p, t = validate_destinations(out_packages, out_truth)
    package_destination = Destination(p)
    try:
        truth_destination = Destination(t)
    except BaseException:
        package_destination.close(success=False)
        raise
    success = False
    try:
        p_stat = os.fstat(package_destination.parent)
        t_stat = os.fstat(truth_destination.parent)
        if (p_stat.st_dev, p_stat.st_ino, package_destination.name) == (
            t_stat.st_dev,
            t_stat.st_ino,
            truth_destination.name,
        ):
            raise ValueError("Output roots are physical aliases of the same directory")
        # Probe optional PDF dependency before writing any artifacts.
        version("reportlab")
        packages = package_destination.stage()
        truth = truth_destination.stage()
        for index in range(1, n + 1):
            deal = first if index == 1 else sample_deal(seed, index=index, priors=priors)
            calculations = calculate_truth(deal)
            deal_dir = packages / deal.deal_id
            deal_dir.mkdir(mode=0o700)
            for layout in RENT_ROLL_COLUMNS:
                for extension in ("xlsx", "csv"):
                    content = rent_roll_bytes(deal, layout=layout, extension=extension)
                    with (deal_dir / f"rent-roll-{layout}.{extension}").open("xb") as handle:
                        handle.write(content)
            with (deal_dir / "t12.xlsx").open("xb") as handle:
                handle.write(t12_bytes(deal))
            render_om(deal, deal_dir / "om.pdf")
            _json(
                truth / f"{deal.deal_id}.json",
                {
                    "schema_version": "1.0.0",
                    "latent": deal.model_dump(mode="json"),
                    "inputs": input_manifest(deal),
                    "calculations": {k: v.model_dump(mode="json") for k, v in calculations.items()},
                    "package_sha256": {
                        f.name: sha256(f.read_bytes()).hexdigest()
                        for f in sorted(deal_dir.iterdir())
                    },
                },
            )
        digest = sha256()
        for source in sorted(Path(__file__).parent.glob("*.py")):
            digest.update(source.name.encode() + b"\0" + source.read_bytes() + b"\0")
        _json(
            truth / "manifest.json",
            {
                "schema_version": "1.0.0",
                "generator_code_sha256": digest.hexdigest(),
                "seed": seed,
                "n": n,
                "priors": priors.model_dump(mode="json"),
                "dependencies": {
                    name: version(name) for name in ("openpyxl", "reportlab", "pydantic")
                },
                "runtime": {
                    "python": platform.python_version(),
                    "zlib": zlib.ZLIB_RUNTIME_VERSION,
                },
                "deal_ids": [f"deal-{i:04d}" for i in range(1, n + 1)],
                "financial_units": {
                    "money": "USD",
                    "rent_and_ledger": "USD/month",
                    "projection_ratios": "decimal fractions",
                },
            },
        )
        # Publish scoring data first: packages appear only once truth is complete.
        truth_destination.publish()
        package_destination.publish()
        success = True
    finally:
        try:
            package_destination.close(success=success)
        finally:
            truth_destination.close(success=success)
