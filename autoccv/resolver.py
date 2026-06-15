"""Resolve human-readable labels to CCV controlled-vocabulary (lov) ids and refTable chains.

Matching order: exact (case-insensitive) -> ASCII-normalised -> difflib fuzzy.
Returns (id/chain, confidence) where confidence in {"exact","fuzzy"} or None when unresolved.
"""
import difflib
import json
import os
from . import clean

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
AUTO = 0.90   # >= -> accept silently
SUGGEST = 0.75  # >= -> return as a candidate to confirm


def _norm(s):
    return clean.to_ascii((s or "")).lower().strip()


class Catalog:
    def __init__(self, data_dir=DATA):
        with open(os.path.join(data_dir, "lov_catalog.json")) as f:
            self.lov = json.load(f)
        with open(os.path.join(data_dir, "reftable_catalog.json")) as f:
            self.reftab = json.load(f)
        # extra org ids harvested from a seed export at runtime (merge overlay)
        self.org_overlay = {}

    # ------------------------------------------------------------- lov
    def resolve_lov(self, field_label, human):
        """-> (lov_id, canonical_label, confidence) or (None, None, None)."""
        table = self.lov.get(field_label)
        if not table or not human:
            return (None, None, None)
        # exact / case-insensitive
        for k, v in table.items():
            if k == human or k.lower() == human.lower():
                return (v, k, "exact")
        # ascii-normalised
        nh = _norm(human)
        for k, v in table.items():
            if _norm(k) == nh:
                return (v, k, "exact")
        # fuzzy
        keys = list(table)
        best, score = None, 0.0
        for k in keys:
            r = difflib.SequenceMatcher(None, nh, _norm(k)).ratio()
            if r > score:
                best, score = k, r
        if best is not None and score >= AUTO:
            return (table[best], best, "fuzzy")
        if best is not None and score >= SUGGEST:
            return (table[best], best, "suggest")
        return (None, None, None)

    def lov_options(self, field_label):
        return self.lov.get(field_label, {})

    # ------------------------------------------------------------- refTable
    def resolve_reftable(self, reftable_label, human):
        """-> (ref_value_id, chain, confidence) or (None, None, None)."""
        bucket = self.reftab.get(reftable_label)
        if not bucket or not human:
            return (None, None, None)
        entries = dict(bucket["entries"])
        if reftable_label == "Organization":
            entries.update(self.org_overlay)
        ref_value_id = bucket.get("refValueId")
        for k, chain in entries.items():
            if k == human or k.lower() == human.lower():
                return (ref_value_id, chain, "exact")
        nh = _norm(human)
        for k, chain in entries.items():
            if _norm(k) == nh:
                return (ref_value_id, chain, "exact")
        best, score = None, 0.0
        for k in entries:
            r = difflib.SequenceMatcher(None, nh, _norm(k)).ratio()
            if r > score:
                best, score = k, r
        if best is not None and score >= AUTO:
            return (ref_value_id, entries[best], "fuzzy")
        if best is not None and score >= SUGGEST:
            return (ref_value_id, entries[best], "suggest")
        return (None, None, None)

    def add_org(self, leaf_value, chain):
        self.org_overlay[leaf_value] = chain
