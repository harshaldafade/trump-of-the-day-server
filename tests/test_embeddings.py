from types import SimpleNamespace

import pytest

from lib import embeddings


class FakeVoyage:
    def __init__(self, dims=embeddings.DIMENSIONS):
        self.batches = []
        self.dims = dims

    def embed(self, texts, model=None, input_type=None):
        self.batches.append((len(texts), model, input_type))
        return SimpleNamespace(embeddings=[[0.5] * self.dims for _ in texts])


def test_document_text_joins_title_and_description():
    assert embeddings.document_text({"title": " T ", "description": " D "}) == "T\n\nD"
    assert embeddings.document_text({"title": "T", "description": None}) == "T"


def test_embed_documents_batches_and_uses_document_input_type():
    client = FakeVoyage()
    vectors = embeddings.embed_documents(["x"] * 300, client=client)
    assert len(vectors) == 300
    assert client.batches == [
        (128, "voyage-3.5", "document"), (128, "voyage-3.5", "document"), (44, "voyage-3.5", "document"),
    ]


def test_embed_documents_rejects_wrong_dimensions():
    with pytest.raises(ValueError):
        embeddings.embed_documents(["x"], client=FakeVoyage(dims=512))


def test_vector_literal():
    assert embeddings.to_vector_literal([0.1, -2, 3.25]) == "[0.1,-2,3.25]"
