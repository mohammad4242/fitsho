# OpenCode Chat Completions Adapter

## Scope

Support OpenCode Zen models that use the OpenAI-compatible Chat Completions API
while preserving the existing Responses API behavior for GPT 5.6 models.

## Endpoint selection

The OpenCode provider selects an API style from the configured model identifier:

- known Responses API models use `/responses`;
- known OpenAI-compatible models, including `nemotron-3-ultra-free`, use
  `/chat/completions`;
- unknown models retain the current `/responses` behavior for compatibility.

The mapping is internal to the provider. No new environment variable is added.

## Request and response handling

For Chat Completions, the provider sends the system prompt as a system message
and the serialized workout payload as a user message. It requests strict JSON
Schema output using the OpenAI-compatible response format.

The provider reads the generated JSON from `choices[0].message.content`, then
uses the existing Pydantic model validation and workout-plan validator. Provider
errors retain the existing safe error mapping.

## Testing

Provider unit tests cover endpoint selection, Chat Completions request shape,
successful parsing, malformed responses, and the unchanged Responses API path.

## Out of scope

Anthropic Messages and Gemini model-specific adapters are not added in this
change.
