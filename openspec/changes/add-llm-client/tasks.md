# Tasks

## 1. Contrato y configuración

- [ ] 1.1 Usar `docs-checker` para confirmar las firmas de `pydantic-settings` y de los SDKs `anthropic` y `openai` en las versiones instaladas
- [ ] 1.2 Definir `LLMSettings`, `LLMResponse`, `Usage` y la jerarquía `LLMError`
- [ ] 1.3 Definir el Protocol `LLMClient` (complete, stream, embed) y la fábrica `build_llm_client`

## 2. Tests primero

- [ ] 2.1 Usar `test-writer` para escribir los tests de todos los escenarios con un proveedor falso programable (fallas N veces, latencia, 429 con Retry-After)
- [ ] 2.2 Confirmar que los tests fallan por la razón correcta

## 3. Implementación

- [ ] 3.1 Proveedor `fake` determinista
- [ ] 3.2 Política de reintentos y timeout
- [ ] 3.3 Adaptadores de Anthropic, OpenAI y Ollama (este último, si se confirma en las preguntas abiertas)
- [ ] 3.4 Log estructurado de uso, con un test que verifica la ausencia del prompt

## 4. Cierre

- [ ] 4.1 Correr `/verify` en verde
- [ ] 4.2 Test de integración opcional (`-m integration`) contra un proveedor real, con la clave tomada del entorno
- [ ] 4.3 Pasar `reviewer` sobre el diff y resolver los hallazgos
- [ ] 4.4 Agregar la sección `llm` al README de `services/ai`
