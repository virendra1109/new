import numpy as np
from openai import AzureOpenAI
from config.kushal_config import config
from utils.loggers import logger

client = AzureOpenAI(
    api_key=config.AZURE_OPENAI_KEY,
    api_version=config.AZURE_OPENAI_VERSION,
    azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
)

def get_embedding(text: str) -> np.ndarray:
    """Generate an embedding vector for given text using Azure OpenAI."""
    logger.debug(f"Generating embedding for text: {text[:50]}...")
    response = client.embeddings.create(
        input=text, model=config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
    )
    return np.array(response.data[0].embedding, dtype=np.float32)
