from dataclasses import dataclass


@dataclass
class VectorDocument:

    content: str
    vector: list[float]
    metadata: dict


class VectorStore:

    async def add(
        self,
        documents: list[VectorDocument],
    ):
        raise NotImplementedError

    async def similarity_search(
        self,
        vector: list[float],
        top_k: int = 5,
    ) -> list[VectorDocument]:

        raise NotImplementedError