from dataclasses import dataclass

@dataclass
class RetrievalResult:
    content: str
    score: float
    metadata: dict


class Retriever:
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievalResult]:

        raise NotImplementedError