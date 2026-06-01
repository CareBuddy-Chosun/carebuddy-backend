"""Ingest the MedQuAD dataset into a FAISS index using LM Studio embeddings.

Reads a cleaned JSONL file (one record per line with keys: question, answer,
combined_text, metadata{source,type}), builds LangChain Documents, embeds them
via the OpenAI-compatible LM Studio endpoint, and persists a FAISS index to
settings.FAISS_INDEX_PATH.

Usage (inside the api container):
    docker compose exec api python scripts/ingest_medical.py --limit 500
    docker compose exec api python scripts/ingest_medical.py --limit 0   # all
"""

import argparse
import json
import os
import sys
import time

# Make the app package importable when run as a plain script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_community.vectorstores import FAISS  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_openai import OpenAIEmbeddings  # noqa: E402

from app.core.config import settings  # noqa: E402

DEFAULT_DATA_PATH = os.environ.get("MEDQUAD_PATH", "/data/medquad_clean.jsonl")


def load_documents(path: str, limit: int) -> list[Document]:
    docs: list[Document] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            content = record.get("combined_text") or record.get("answer") or ""
            if not content:
                continue
            meta = record.get("metadata") or {}
            docs.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": meta.get("source", ""),
                        "type": meta.get("type", ""),
                        "question": record.get("question", ""),
                    },
                )
            )
            if limit and len(docs) >= limit:
                break
    return docs


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest MedQuAD into FAISS.")
    parser.add_argument(
        "--path", default=DEFAULT_DATA_PATH, help="Path to medquad_clean.jsonl"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Max records to ingest (0 = all).",
    )
    args = parser.parse_args()

    print(f"[ingest] reading {args.path} (limit={args.limit})")
    docs = load_documents(args.path, args.limit)
    print(f"[ingest] loaded {len(docs)} documents")
    if not docs:
        print("[ingest] no documents to ingest, aborting.")
        sys.exit(1)

    embeddings = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_base=settings.OPENAI_BASE_URL,
        openai_api_key=settings.OPENAI_API_KEY,
        check_embedding_ctx_length=False,
    )

    print(
        f"[ingest] embedding via {settings.OPENAI_BASE_URL} "
        f"model={settings.EMBEDDING_MODEL}"
    )
    start = time.time()
    vectorstore = FAISS.from_documents(docs, embeddings)
    elapsed = time.time() - start
    print(f"[ingest] built FAISS index of {len(docs)} docs in {elapsed:.1f}s")

    os.makedirs(settings.FAISS_INDEX_PATH, exist_ok=True)
    vectorstore.save_local(settings.FAISS_INDEX_PATH)
    print(f"[ingest] saved index to {settings.FAISS_INDEX_PATH}")


if __name__ == "__main__":
    main()
