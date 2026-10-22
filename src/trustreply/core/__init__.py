"""Core engine: ingestion, retrieval and answer drafting. No web or CLI code here."""

from trustreply.core.ingest import ingest_path
from trustreply.core.models import Chunk

__all__ = ["Chunk", "ingest_path"]
