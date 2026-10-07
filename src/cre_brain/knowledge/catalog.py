from importlib.resources import files

from cre_brain.knowledge.models import Catalog


def catalog_bytes() -> bytes:
    return files("cre_brain.knowledge").joinpath("catalog.json").read_bytes()


def load_catalog() -> Catalog:
    """The installed, reviewed catalog is the only ingestion authority."""
    return Catalog.model_validate_json(catalog_bytes())
