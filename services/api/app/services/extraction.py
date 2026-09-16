from __future__ import annotations

import re
from typing import Any
from jsonschema import Draft202012Validator
from sqlalchemy.orm import Session
from .retrieval import RetrievalService


class StructuredExtractionService:
    def __init__(self, db: Session):
        self.db = db

    async def extract(self, *, workspace_id: str, document_ids: list[str], schema: dict[str, Any]) -> dict[str, Any]:
        Draft202012Validator.check_schema(schema)
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise ValueError("Schema properties must be an object")
        hits = await RetrievalService(self.db).search(
            workspace_id=workspace_id,
            query=" ".join(properties.keys()) or "document information",
            document_ids=document_ids,
            limit=30,
        )
        corpus = "\n".join(hit.text for hit in hits)
        result: dict[str, Any] = {}
        for field, spec in properties.items():
            expected = spec.get("type") if isinstance(spec, dict) else None
            pattern = re.compile(rf"(?im)^\s*{re.escape(field).replace('_', r'[ _-]')}\s*[:\-]\s*(.+?)\s*$")
            match = pattern.search(corpus)
            raw = match.group(1).strip() if match else None
            if raw is None:
                if isinstance(expected, list) and "null" in expected:
                    result[field] = None
                elif expected == "string":
                    result[field] = ""
                elif expected in {"number", "integer"}:
                    result[field] = 0
                elif expected == "array":
                    result[field] = []
                elif expected == "object":
                    result[field] = {}
                else:
                    result[field] = None
                continue
            if expected == "integer":
                number = re.search(r"-?\d+", raw)
                result[field] = int(number.group()) if number else 0
            elif expected == "number":
                number = re.search(r"-?\d+(?:\.\d+)?", raw.replace(",", ""))
                result[field] = float(number.group()) if number else 0.0
            elif expected == "array":
                result[field] = [part.strip() for part in re.split(r"[,;]", raw) if part.strip()]
            else:
                result[field] = raw
        errors = sorted(Draft202012Validator(schema).iter_errors(result), key=lambda e: list(e.path))
        if errors:
            raise ValueError("Extraction failed schema validation: " + "; ".join(error.message for error in errors[:5]))
        return {"data": result, "sources": [
            {"chunk_id": h.chunk_id, "document_id": h.document_id, "page_number": h.page_number, "excerpt": h.text[:300]}
            for h in hits[:8]
        ]}
