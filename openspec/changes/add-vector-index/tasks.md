# Tasks

## 1. Contrato

- [ ] 1.1 Usar `docs-checker` para confirmar las APIs async de `qdrant-client` y de `faiss-cpu`
- [ ] 1.2 Definir los modelos `Chunk` y `SearchHit`, el Protocol `VectorStore` y el chunker de la línea base

## 2. Tests primero

- [ ] 2.1 Usar `test-writer` para escribir los tests de los escenarios: FAISS en memoria para la CI rápida y Qdrant como `integration`
- [ ] 2.2 Confirmar que los tests fallan

## 3. Implementación

- [ ] 3.1 Chunker
- [ ] 3.2 Adaptador de FAISS
- [ ] 3.3 Adaptador de Qdrant y servicio en compose
- [ ] 3.4 Script `evals/bench_vector.py` con su salida en `evals/bench/`

## 4. Cierre

- [ ] 4.1 Correr `/verify` en verde, ejecutar el benchmark y commitear la tabla
- [ ] 4.2 Escribir el ADR corto con la elección de backend y su justificación numérica en `design.md`
- [ ] 4.3 Pasar `reviewer`
