# Model Tool Support Matrix

## Overview

Not all LLM models support tool/function calling. This document tracks which models support tools and how the router handles them.

## Tool Support by Model

| Model | Tools Supported | Route | Backend | Notes |
|-------|----------------|-------|---------|-------|
| **gpt-oss:20b** | ✅ Yes | SELF_HANDLE, REASONING, ROUTER | Ollama | Supports web_search, fetch_webpage |
| **gpt-oss-120b-eagle3** | ✅ Yes | COMPLEX_CODE, REASONING, RESEARCH | SGLang | Eagle3 speculative decoding (1.6-1.8× speedup). Supports web_search, fetch_webpage via OpenAI-compatible API. 128GB systems only. |
| **qwen2.5-coder:7b** | ✅ Yes | SIMPLE_CODE | Ollama | Supports tools for coding tasks |
| **deepseek-r1:8b** | ❌ No | - (Not currently used) | Ollama | Pure reasoning model, no tool support |
| **deepseek-r1:14b** | ❌ No | - | Ollama | Pure reasoning model, no tool support |
| **deepseek-r1:32b** | ❌ No | - | Ollama | Pure reasoning model, no tool support |

**Note**: All currently active routes (SELF_HANDLE, SIMPLE_CODE, REASONING, RESEARCH, COMPLEX_CODE) use models that support tools. The conditional tool provision logic remains in place for future flexibility.

## Implementation

### Conditional Tool Provision

The `generate_with_route()` method in [strands_llm.py](app/implementations/strands_llm.py) conditionally provides tools based on the model:

```python
# Conditionally provide tools based on model
# deepseek-r1 models don't support tool calling (pure reasoning models)
agent_tools = []
if 'deepseek-r1' not in model.lower():
    # Only provide tools for models that support them
    from app.tools import web_search
    limiter = CallLimiter(max_calls=2)
    stripper = ContentStripper()
    limited_fetch = create_limited_fetch_wrapper(
        self.base_fetch_webpage,
        limiter=limiter,
        stripper=stripper
    )
    agent_tools = [web_search, limited_fetch]
    logger.info(f"🔧 Providing tools (web_search, fetch_webpage) to {model}")
else:
    logger.info(f"🧠 Pure reasoning mode for {model} (no tools)")
```

### Route-Specific Behavior

#### SELF_HANDLE Route (gpt-oss:20b)
- **Tools**: ✅ web_search, fetch_webpage
- **Use case**: Quick questions that may need web lookups
- **Prompt**: Mentions web search capabilities

#### SIMPLE_CODE Route (qwen2.5-coder:7b)
- **Tools**: ✅ web_search, fetch_webpage
- **Use case**: Coding tasks that may reference documentation
- **Prompt**: Focuses on coding principles

#### REASONING Route (gpt-oss:20b)
- **Tools**: ✅ web_search, fetch_webpage
- **Use case**: Deep analysis, comparisons, research questions
- **Prompt**: Mentions web search for current/factual questions
- **Why gpt-oss**: Good balance of reasoning ability and tool support for research

## Error Example

When tools are provided to unsupported models:

```
Error: LLM generation failed: registry.ollama.ai/library/deepseek-r1:8b
does not support tools (status code: 400)
```

## Adding New Models

When adding a new model:

1. **Check tool support**: Test if the model supports function/tool calling
2. **Update matrix**: Add entry to this document
3. **Update conditional logic**: Add model pattern to tool provision logic if needed
4. **Update route prompts**: Adjust system prompts based on tool availability

### Example: Adding a new model

```python
# In strands_llm.py
if 'deepseek-r1' not in model.lower() and 'new-model-name' not in model.lower():
    # Provide tools
    agent_tools = [web_search, limited_fetch]
else:
    # No tools for reasoning-only models
    agent_tools = []
```

## Best Practices

1. **Always check tool support** before assigning models to routes
2. **Log tool provision** to make debugging easier
3. **Update prompts** to match tool availability (don't mention web tools if not available)
4. **Test thoroughly** when adding new models
5. **Document tool support** in this file

## Related Files

- [strands_llm.py](app/implementations/strands_llm.py) - Tool provision logic
- [router_service.py](app/services/router_service.py) - Route classification
- [config.py](app/config.py) - Model configuration

## References

- deepseek-r1 models are designed for chain-of-thought reasoning without tool use
- Most modern LLMs (GPT, Claude, Qwen-Coder) support function calling
- Tool support is model-specific, not provider-specific (Ollama itself supports tools)
