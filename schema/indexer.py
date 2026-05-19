from __future__ import annotations

import json
import pickle
import time
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from core.db import load_full_schema
from utils.logger import get_logger

logger = get_logger(__name__)


_CACHE_DIR   = Path(__file__).parent.parent / ".cache"
_INDEX_PATH  = _CACHE_DIR / "schema.faiss"
_META_PATH   = _CACHE_DIR / "schema_meta.pkl"
_SCHEMA_PATH = _CACHE_DIR / "schema_raw.json"
_CACHE_DIR.mkdir(exist_ok=True)

_MODEL_NAME = "all-MiniLM-L6-v2"
_embedder: SentenceTransformer | None = None

MIN_SCORE = 0.25   

def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        logger.info("Loading embedding model '%s'…", _MODEL_NAME)
        _embedder = SentenceTransformer(_MODEL_NAME)
    return _embedder


_DOMAIN_HINTS: dict[str, str] = {
    "F_COMPTET":       "customers suppliers tiers clients fournisseurs third-parties accounts",
    "F_DOCENTETE":     "documents invoices orders quotes purchases sales headers bon commande facture devis",
    "F_DOCLIGNE":      "document lines invoice lines order lines article quantity price detail lignes",
    "F_ARTICLE":       "articles products items references stock catalog produits",
    "F_FAMILLE":       "families product families categories familles",
    "F_CREGLEMENT":    "payments settlements règlements paiements encaissements",
    "F_REGLEMENTT":    "payment methods modes de règlement types paiement",
    "F_BANQUE":        "bank accounts banque comptes bancaires IBAN",
    "F_TAXE":          "tax rates TVA taxes taux",
    "F_JOURNAUX":      "journals journaux comptables",
    "F_ECRITUREC":     "accounting entries écritures comptables journal entries",
    "F_ARTSTOCK":      "stock inventory quantités en stock par dépôt",
    "F_DEPOT":         "warehouses depots dépôts magasins",
    "F_COLLABORATEUR": "collaborators sales reps commerciaux représentants employees",
    "F_TARIF":         "price lists tarifs prix articles",
    "F_IMMOBILISATION":"fixed assets immobilisations actifs",
    "F_ECHEANCES":     "due dates maturities échéances",
    "F_COMPTEG":       "general ledger accounts plan comptable comptes généraux",
    "F_COMPTET":       "third party accounts tiers customers suppliers",
    "F_AGENDA":        "agenda calendar events rendez-vous",
    "F_PREVISION":     "forecasts prévisions budget",
    "F_CAISSE":        "cash register caisse paiements espèces",
    "F_LOYER":         "rent loyer bail",
    "F_ABONNEMENT":    "subscriptions abonnements recurring",
    "F_CONDITION":     "conditions payment terms délais règlement",
}


def _build_chunk(table: str, info: dict) -> str:
   
    cols = info["columns"]
    pks  = set(info["primary_keys"])
    fks  = info["foreign_keys"]

    
    col_lines: list[str] = []
    for c in cols:
        tags: list[str] = []
        if c["name"] in pks:
            tags.append("PRIMARY KEY")
        fk_match = [fk for fk in fks if fk["column"] == c["name"]]
        for fk in fk_match:
            tags.append(f"FK → {fk['ref_table']}.{fk['ref_column']}")
        tag_str = f"  [{', '.join(tags)}]" if tags else ""
        col_lines.append(f"    {c['name']}  {c['type']}{tag_str}")

    
    rel_lines: list[str] = []
    for fk in fks:
        if fk["column"] and fk["ref_table"]:
            rel_lines.append(
                f"  {table}.{fk['column']} joins {fk['ref_table']}.{fk['ref_column']}"
            )

    
    hint = _DOMAIN_HINTS.get(table, "")

    parts = [
        f"Table name: {table}",
    ]
    if hint:
        parts.append(f"Domain keywords: {hint}")
    parts.append(f"Columns ({len(cols)}):")
    parts.extend(col_lines)
    if rel_lines:
        parts.append("Relationships:")
        parts.extend(rel_lines)

    return "\n".join(parts)



_QUERY_EXPANSIONS: dict[str, str] = {
    "customer":    "customer tiers comptet client F_COMPTET CT_Type=0",
    "customers":   "customers tiers comptet clients F_COMPTET CT_Type=0",
    "supplier":    "supplier tiers comptet fournisseur F_COMPTET CT_Type=1",
    "suppliers":   "suppliers tiers comptet fournisseurs F_COMPTET CT_Type=1",
    "invoice":     "invoice facture document docentete F_DOCENTETE DO_Type=6",
    "invoices":    "invoices factures documents docentete F_DOCENTETE DO_Type=6",
    "order":       "order commande document docentete F_DOCENTETE DO_Type=2",
    "orders":      "orders commandes documents docentete F_DOCENTETE",
    "quote":       "quote devis document docentete F_DOCENTETE DO_Type=1",
    "product":     "product article F_ARTICLE AR_Ref AR_Design",
    "products":    "products articles F_ARTICLE",
    "stock":       "stock inventory F_ARTSTOCK F_ARTICLE AS_QteSto",
    "payment":     "payment règlement F_CREGLEMENT F_REGLEMENTT",
    "payments":    "payments règlements F_CREGLEMENT",
    "bank":        "bank banque F_BANQUE BQ_IBAN",
    "tax":         "tax TVA F_TAXE TA_Taux",
    "journal":     "journal comptable F_JOURNAUX F_ECRITUREC",
    "entry":       "accounting entry écriture F_ECRITUREC",
    "entries":     "accounting entries écritures F_ECRITUREC",
    "warehouse":   "warehouse depot dépôt F_DEPOT",
    "asset":       "fixed asset immobilisation F_IMMOBILISATION",
    "assets":      "fixed assets immobilisations F_IMMOBILISATION",
    "price":       "price tarif F_TARIF F_ARTICLE AR_PrixVen",
    "sales rep":   "sales rep collaborateur commercial F_COLLABORATEUR",
    "family":      "family famille F_FAMILLE FA_CodeFamille",
    "families":    "families familles F_FAMILLE",
}


def _expand_query(question: str) -> str:
    
    q_lower = question.lower()
    extra: list[str] = []
    for keyword, expansion in _QUERY_EXPANSIONS.items():
        if keyword in q_lower:
            extra.append(expansion)
    if extra:
        return question + " " + " ".join(extra)
    return question




def build_index(force: bool = False) -> None:
    """
    Introspect DB, embed all table chunks, build and persist FAISS index.
    
    """
    if not force and _INDEX_PATH.exists() and _META_PATH.exists():
        logger.info("Schema index already on disk — skipping build (use force=True to rebuild).")
        return

    t0 = time.perf_counter()
    logger.info("Building schema index…")

    schema = load_full_schema()
    _SCHEMA_PATH.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    table_names: list[str] = []
    chunks:      list[str] = []

    for table, info in schema.items():
        table_names.append(table)
        chunks.append(_build_chunk(table, info))

    logger.info("Embedding %d table chunks…", len(chunks))

    embedder   = _get_embedder()
    embeddings = embedder.encode(
        chunks,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    embeddings = np.array(embeddings, dtype="float32")

    dim   = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    faiss.write_index(index, str(_INDEX_PATH))
    with open(_META_PATH, "wb") as f:
        pickle.dump(
            {"table_names": table_names, "chunks": chunks, "schema": schema},
            f,
        )

    elapsed = time.perf_counter() - t0
    logger.info("Index built: %d tables, dim=%d, %.1fs", len(table_names), dim, elapsed)




class SchemaRetriever:
    """
    Semantic retrieval of relevant table schemas for a user question.
    
    """

    def __init__(self, top_k: int = 8):
        self.top_k  = top_k
        self._index = None
        self._meta  = None

    def _load(self) -> None:
        if self._index is not None:
            return
        if not _INDEX_PATH.exists():
            logger.info("No index found — building now…")
            build_index()
        logger.info("Loading schema index from disk…")
        self._index = faiss.read_index(str(_INDEX_PATH))
        with open(_META_PATH, "rb") as f:
            self._meta = pickle.load(f)

    def retrieve(self, question: str) -> list[dict[str, Any]]:
        """
        Returns top-K most relevant tables for the question, filtered
        by MIN_SCORE cosine similarity threshold.

        Return format:
        [
          {
            "table":  "F_COMPTET",
            "score":  0.91,
            "chunk":  "Table name: F_COMPTET\n...",
            "schema": {"columns": [...], "primary_keys": [...], "foreign_keys": [...]}
          },
        ]
        """
        self._load()

        
        expanded = _expand_query(question)
        logger.debug("Expanded query: %s", expanded[:120])

        embedder = _get_embedder()
        q_vec    = embedder.encode(
            [expanded], normalize_embeddings=True
        ).astype("float32")

        scores, indices = self._index.search(q_vec, self.top_k)

        results: list[dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or float(score) < MIN_SCORE:
                continue
            table = self._meta["table_names"][idx]
            results.append({
                "table":  table,
                "score":  float(score),
                "chunk":  self._meta["chunks"][idx],
                "schema": self._meta["schema"][table],
            })

        logger.info(
            "Retrieved %d tables for '%s': %s",
            len(results),
            question[:60],
            [r["table"] for r in results],
        )
        return results

    def get_schema_context(self, question: str) -> str:
        """
        Formatted schema string to inject into the LLM prompt.
        Includes only the top-K relevant tables.
        """
        results = self.retrieve(question)
        if not results:
            return "No highly relevant tables found — use the domain hints in your system prompt."

        lines = [
            "Relevant Sage 100 tables (retrieved by semantic similarity):",
            "",
        ]
        for r in results:
            lines.append(r["chunk"])
            lines.append("")   

        return "\n".join(lines)

    def list_all_tables(self) -> list[str]:
        self._load()
        return list(self._meta["table_names"])