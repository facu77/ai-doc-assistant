# Design

## Context

Consumen esta capa el RAG (`add-rag-core`) y el agente. Los chunks llevan los metadatos `doc_id`, `page`, `chunk_id`, `section` y `acl_groups` (este último se usa en `add-observability-security`).

## Goals / Non-Goals

**Goals:**
- Que cambiar de backend sea solo cambiar `VECTOR_BACKEND`.
- Un benchmark reproducible, con semilla, que guarde su resultado en JSON.

**Non-Goals:**
- Búsqueda híbrida y reranking (`add-rag-core`).
- Sharding o replicación de Qdrant.

## Decisions

- **Chunking de la línea base**: 800 tokens con un solapamiento de 100, respetando los límites de página.
- **Qdrant**: distancia coseno, índice HNSW con parámetros por defecto, payload index sobre `doc_id` y `acl_groups`. Se usa el cliente async.
- **FAISS**: `IndexFlatIP` como referencia exacta y `IndexHNSWFlat` como aproximado. Los filtros se resuelven con pre-filtrado por IDs.
- **Recall@10**: es la intersección entre los top-10 del backend y los top-10 exactos, dividida por 10, promediada sobre N consultas.
- **El benchmark** corre las mismas consultas en el mismo orden, con 5 de calentamiento descartadas.

## Risks / Trade-offs

- FAISS en proceso no tiene persistencia ni filtros nativos ricos. Es parte de la conclusión del benchmark, no un defecto que haya que esconder.
