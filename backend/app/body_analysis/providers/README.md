# Body-analysis AI providers

`AIProvider` is the stable boundary used by body-analysis jobs and future admin
configuration. `OpenRouterProvider` is the first adapter and uses an injected
`httpx.AsyncClient`; credentials and task routing are supplied by the caller and
are never persisted here.

Model IDs are provider-specific. The OpenRouter catalog is fetched dynamically
from `/api/v1/models`, normalized into `ModelCapabilities`, and can be filtered
for image input or structured output. Structured generation has bounded model
fallbacks and at most one schema-repair request across the complete route.

New providers should implement `AIProvider`, return the shared normalized models
and errors, and keep provider request/response envelopes inside their adapter.
