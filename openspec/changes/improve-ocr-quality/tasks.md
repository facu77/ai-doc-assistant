# Tasks

## 1. Preparación

- [ ] 1.1 Escribir los deltas de spec sobre `document-ingestion` ya archivada y sacar `skip_specs` de `.openspec.yaml`
- [ ] 1.2 Responder las preguntas abiertas de la propuesta (reutilizar el corpus de prueba, umbral del perfil ruidoso v2, presupuesto de tiempo)
- [ ] 1.3 Preregistrar en `design.md` las reglas de decisión (candidatos, métrica y empates) antes de generar datos o medir
- [ ] 1.4 Generar el set de validación nuevo (dos columnas, tablas, formularios y texto corrido) con otra semilla

## 2. Tests primero

- [ ] 2.1 Escribir los tests de los escenarios nuevos con fakes sensibles a la imagen (por ejemplo, que reciban dos columnas o una tabla y devuelvan el texto en el orden que lee el psm)
- [ ] 2.2 Escribir el test de integración del perfil ruidoso v2 con su umbral preregistrado

## 3. Estructura de página y tablas

- [ ] 3.1 Implementar los candidatos: detección de layout o tablas, psm por página, elección por confianza, orden de lectura desde `image_to_data`
- [ ] 3.2 Medir los candidatos sobre la validación, aplicar la regla y versionar las corridas en `evals/runs/ingest/`
- [ ] 3.3 Correr una sola vez el corpus de prueba con el candidato elegido y reportar el resultado tal cual
- [ ] 3.4 Si el escaneo limpio queda en ≤ 2 %, sacar el `xfail(strict=True)` de `test_cer_medio_de_escaneos_limpios_es_a_lo_sumo_2_por_ciento`

## 4. Perfil ruidoso v2

- [ ] 4.1 Agregar el perfil `noisy_scan_v2` al generador (desenfoque, bajo contraste, manchas, textura, 150 dpi) sin cambiar el corpus existente
- [ ] 4.2 Medirlo, compararlo con su umbral y reportarlo aparte

## 5. Cierre

- [ ] 5.1 Correr `/verify` y `pytest -m integration` en verde
- [ ] 5.2 Actualizar README, `REPORT.md` y `evals/RESULTS.md`, y subir `PIPELINE_VERSION`
- [ ] 5.3 Pasar `reviewer` y escribir `docs/aprendizaje/<nº>-improve-ocr-quality.md`
