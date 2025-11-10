import numpy as np
from openai import AzureOpenAI
from config.config import config

client = AzureOpenAI(
    api_key=config.AZURE_OPENAI_KEY,
    api_version=config.AZURE_OPENAI_VERSION,
    azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
)


def get_embedding(text: str) -> np.ndarray:
    """Generate embedding vector for text using Azure OpenAI."""
    response = client.embeddings.create(
        input=text, 
        model=config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
    )
    return np.array(response.data[0].embedding, dtype=np.float32)