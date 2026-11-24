"""Document embeddings for semantic search and "related coverage".

The API embeds search queries with the same model (input_type "query"); keep
MODEL and DIMENSIONS in sync with api/src/embeddings.ts in the parent repo and
the vector(1024) column in db/schema.sql.
"""

import os

MODEL = "voyage-3.5"
DIMENSIONS = 1024
BATCH_SIZE = 128

# Each vector costs about 12 KB once its HNSW index entry is counted, against about
# 2 KB for the story without one, so only each day's best-ranked stories are embedded.
# Search and "related coverage" cover those; the rest stay in the feed unembedded.
DEFAULT_TOP_PER_DAY = 50


def top_per_day():
    """How many of each day's stories (by relevance_score) get an embedding.

    EMBED_TOP_PER_DAY overrides the default; 0 means no limit (embed everything).
    Returns None for no limit. A value that isn't a number falls back to the default.
    """
    raw = os.getenv("EMBED_TOP_PER_DAY", "").strip()
    if not raw:
        return DEFAULT_TOP_PER_DAY
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_TOP_PER_DAY
    return value if value > 0 else None


def document_text(row):
    """What gets embedded for an article: headline plus publisher description."""
    title = (row.get("title") or "").strip()
    description = (row.get("description") or "").strip()
    return f"{title}\n\n{description}" if description else title


def embed_documents(texts, client=None):
    """Embed `texts` in batches; returns one 1024-float list per input, in order."""
    if client is None:
        import voyageai  # imported lazily so the scraper runs without it installed

        client = voyageai.Client()
    vectors = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]
        result = client.embed(batch, model=MODEL, input_type="document")
        vectors.extend(result.embeddings)
    if any(len(v) != DIMENSIONS for v in vectors):
        raise ValueError(f"expected {DIMENSIONS}-dimension embeddings from {MODEL}")
    return vectors


def to_vector_literal(vector):
    """pgvector's text input format, e.g. '[0.1,0.2]'."""
    return "[" + ",".join(f"{x:.7g}" for x in vector) + "]"


def is_configured():
    return bool(os.getenv("VOYAGE_API_KEY"))
