import json
import os
import hashlib
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

CACHE_FILE = Path("cache/verified_claims.json")

class LocalCacheClient:

    def __init__(self):
        CACHE_FILE.parent.mkdir(exist_ok=True)
        if not CACHE_FILE.exists():
            CACHE_FILE.write_text("[]")

    def _load(self):
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))

    def _save(self, data):
        CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _cosine(self, a, b):
        a, b = np.array(a), np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

    def hybrid_search(self, claim_embedding, query_text, top_k=5):
        docs = self._load()
        now = datetime.now(timezone.utc)
        results = []
        for doc in docs:
            ttl = doc.get("ttl_days", 30)
            verified_at = datetime.fromisoformat(doc["verified_at"])
            if (now - verified_at).days > ttl:
                continue
            score = self._cosine(claim_embedding, doc["claim_embedding"])
            results.append({**doc, "_score": score})
        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:top_k]

    def index_verification(self, doc):
        docs = self._load()
        doc["verified_at"] = datetime.now(timezone.utc).isoformat()
        # Reemplaza si ya existe el mismo hash
        docs = [d for d in docs if d.get("claim_hash") != doc.get("claim_hash")]
        docs.append(doc)
        self._save(docs)
        return True

    def get_by_hash(self, claim_hash):
        for doc in self._load():
            if doc.get("claim_hash") == claim_hash:
                now = datetime.now(timezone.utc)
                verified_at = datetime.fromisoformat(doc["verified_at"])
                if (now - verified_at).days <= doc.get("ttl_days", 30):
                    return doc
        return None

    def connect(self): pass
    def close(self): pass