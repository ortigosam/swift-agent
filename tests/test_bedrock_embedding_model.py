import asyncio

from infrastructure.embeddings.bedrock_embedding_model import (
    BedrockEmbeddingModel,
)


async def main():

    model = BedrockEmbeddingModel(
        region_name="eu-central-1",
    )

    text = """
    CashbackRepositoryImpl.getCashback obtains cashback
    information from the CashbackDataSource.
    """

    embedding = await model.embed(text)

    print("Embedding dimensions:", len(embedding))
    print("First values:", embedding[:10])


asyncio.run(main())