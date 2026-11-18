"""Document embeddings for semantic search and "related coverage".

The API embeds search queries with the same model (input_type "query"); keep
MODEL and DIMENSIONS in sync with api/src/embeddings.ts in the parent repo and
the vector(1024) column in db/schema.sql.
"""

import os

MODEL = "voyage-3.5"
DIMENSIONS = 1024
BATCH_SIZE = 128


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
