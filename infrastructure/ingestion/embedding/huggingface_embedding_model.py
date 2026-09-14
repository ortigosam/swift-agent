from __future__ import annotations

from infrastructure.ingestion.embedding.embedding_model import (
    EmbeddingModel,
)


DEFAULT_HUGGINGFACE_EMBEDDING_MODEL = (
    "Qwen/Qwen3-Embedding-0.6B"
)


class HuggingFaceEmbeddingModel(EmbeddingModel):

    _model_cache = {}

    def __init__(
        self,
        model_name: str = DEFAULT_HUGGINGFACE_EMBEDDING_MODEL,
        *,
        device: str | None = None,
        batch_size: int = 16,
        normalize_embeddings: bool = True,
    ):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                "HuggingFaceEmbeddingModel requires the optional "
                "embedding dependencies. Install them with: "
                "uv sync --extra embeddings"
            ) from error

        self._model_name = model_name
        self._batch_size = batch_size
        self._normalize_embeddings = normalize_embeddings
        cache_key = (
            model_name,
            device,
        )
        model = self._model_cache.get(cache_key)

        if model is None:
            model = SentenceTransformer(
                model_name,
                device=device,
            )
            self._model_cache[cache_key] = model

        self._model = model

    @property
    def model_id(self) -> str:
        return self._model_name

    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        if not texts:
            return []

        embeddings = self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=self._normalize_embeddings,
            show_progress_bar=False,
        )

        return [
            [float(value) for value in embedding]
            for embedding in embeddings
        ]
