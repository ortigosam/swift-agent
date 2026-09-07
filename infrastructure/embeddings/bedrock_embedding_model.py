# infrastructure/embeddings/bedrock_embedding_model.py

import asyncio
import json

import boto3

from infrastructure.embeddings.embedding_model import (
    EmbeddingModel,
)


class BedrockEmbeddingModel(EmbeddingModel):

    MODEL_ID = "amazon.titan-embed-text-v2:0"

    def __init__(
        self,
        region_name: str,
        dimensions: int = 1024,
        normalize: bool = True,
    ):
        self.dimensions = dimensions
        self.normalize = normalize

        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region_name,
        )

    async def embed(
        self,
        text: str,
    ) -> list[float]:

        if not text.strip():
            raise ValueError(
                "Cannot generate embedding for empty text"
            )

        response = await asyncio.to_thread(
            self.client.invoke_model,
            modelId=self.MODEL_ID,
            body=json.dumps(
                {
                    "inputText": text,
                    "dimensions": self.dimensions,
                    "normalize": self.normalize,
                }
            ),
        )

        body = json.loads(
            response["body"].read()
        )

        return body["embedding"]

    async def embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        return [
            await self.embed(text)
            for text in texts
        ]