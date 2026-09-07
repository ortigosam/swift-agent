from infrastructure.retrieval.retriever import (
    Retriever,
    RetrievalResult,
)

class InMemoryRetriever(Retriever):

    def __init__(self, documents: list[str]):

        self.documents = documents

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievalResult]:

        query_words = set(
            query.lower().split()
        )

        results = []

        for document in self.documents:

            document_words = set(
                document.lower().split()
            )

            common_words = (
                query_words & document_words
            )

            score = len(common_words)

            if score > 0:

                results.append(
                    RetrievalResult(
                        content=document,
                        score=float(score),
                        metadata={},
                    )
                )

        results.sort(
            key=lambda result: result.score,
            reverse=True,
        )

        return results[:top_k]