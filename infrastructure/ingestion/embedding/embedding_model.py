from __future__ import annotations

from typing import Protocol


class EmbeddingModel(Protocol):

    @property
    def model_id(self) -> str:
        raise NotImplementedError

    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        raise NotImplementedError

    def embed_one(
        self,
        text: str,
    ) -> list[float]:
        return self.embed([text])[0]
