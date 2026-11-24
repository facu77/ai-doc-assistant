"""Cliente LLM independiente del proveedor.

Uso típico (al arrancar el servicio):

    client = build_llm_client()            # lee LLM_* del entorno; falla si algo falta
    respuesta = await client.complete("...")

Importar este paquete no carga ningún SDK: los adaptadores se importan en la fábrica
solo para el proveedor elegido.
"""

from ai_doc_assistant.llm.client import LLMClient
from ai_doc_assistant.llm.errors import (
    LLMConfigError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMValidationError,
)
from ai_doc_assistant.llm.factory import PROVIDERS, build_llm_client
from ai_doc_assistant.llm.models import LLMResponse, Usage
from ai_doc_assistant.llm.resilient import ResilientLLMClient
from ai_doc_assistant.llm.retry import RetryPolicy
from ai_doc_assistant.llm.settings import DEFAULT_LLM_MODEL, LLMSettings, load_llm_settings

__all__ = [
    "DEFAULT_LLM_MODEL",
    "PROVIDERS",
    "LLMClient",
    "LLMConfigError",
    "LLMError",
    "LLMProviderError",
    "LLMRateLimitError",
    "LLMResponse",
    "LLMSettings",
    "LLMTimeoutError",
    "LLMValidationError",
    "ResilientLLMClient",
    "RetryPolicy",
    "Usage",
    "build_llm_client",
    "load_llm_settings",
]
