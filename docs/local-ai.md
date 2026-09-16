# Local AI mode

DocMind supports two credential-free development modes.

## Deterministic mock mode

This is the default and the mode used by CI. It uses deterministic feature-hash embeddings and a grounded mock generator. It exists to test product behavior, isolation and citations—not to claim production semantic quality.

```env
AI_MODE=mock
LLM_PROVIDER=mock
EMBEDDING_PROVIDER=hash
```

## Ollama mode

Start the optional Docker profile and configure models:

```bash
docker compose --profile local-ai up -d
docker exec -it <ollama-container> ollama pull qwen2.5:7b
docker exec -it <ollama-container> ollama pull nomic-embed-text
```

```env
AI_MODE=local
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=ollama
OLLAMA_CHAT_MODEL=qwen2.5:7b
OLLAMA_EMBED_MODEL=nomic-embed-text
```

Embedding dimensions must match the configured database vector dimension. Re-embed existing chunks when changing embedding models.
