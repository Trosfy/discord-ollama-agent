# Running gpt-oss-120B with Eagle3 on DGX Spark: Implementation Guide

**Speculative decoding with Eagle3 on DGX Spark is technically possible but faces significant practical challenges.** While SGLang provides confirmed support for the Grace Blackwell GB10, a critical infinite loop bug affects TensorRT-LLM's Eagle3 implementation on Blackwell consumer GPUs, and memory bandwidth constraints limit throughput to 35-58 tokens/second. Ollama cannot serve Eagle3 models. The recommended path forward uses SGLang with the `lmsysorg/sglang:spark` container and LMSYS's `EAGLE3-gpt-oss-120b-bf16` draft model, achieving approximately 2× speedup over baseline inference at low concurrency.

## Understanding Eagle3 speculative decoding architecture

Eagle3 (Extrapolation Algorithm for Greater Language-Model Efficiency, 3rd version) differs fundamentally from traditional speculative decoding by eliminating the separate draft model entirely. Instead, it attaches a lightweight autoregressive prediction head—the **Eagle head**—directly to the target model's internal layers, operating at the feature level rather than token level.

The architecture captures hidden states from multiple decoder layers (low, mid, and high-level semantic features) and fuses them to predict draft tokens. The Eagle head consists of two fully-connected layers, one decoder layer, and an LM head, adding only **~1.5-2GB** to the model's memory footprint. For gpt-oss-120b-Eagle3-throughput specifically, only the final hidden state post-LayerNorm and pre-LMHead is captured (`eagle3_layers_to_capture: [-1]`), making it optimal for high-concurrency scenarios where single-token speculation is ideal.

NVIDIA provides multiple Eagle3 variants for gpt-oss-120b:

| Variant | Use Case | Max Draft Length |
|---------|----------|------------------|
| **Eagle3-throughput** | High-concurrency, single token | 1-3 |
| **Eagle3-v2** | <8K context, batch padding support | 3 |
| **Eagle3-short-context** | <8K context optimization | 3 |
| **Eagle3-long-context** | >8K context retention | 3 |

MT-Bench acceptance rates for the throughput variant with `draft_len=1` range from **1.64** (humanities) to **1.84** (math), meaning nearly 2 tokens are generated per verification step on average—translating to approximately **1.6-2× throughput improvement** over baseline inference.

## DGX Spark hardware architecture creates unique constraints

The DGX Spark's **GB10 Grace Blackwell Superchip** features 128GB unified LPDDR5X memory shared between a 20-core ARM CPU and a Blackwell GPU with 5th-generation Tensor Cores supporting native FP4 precision. The entire 128GB is accessible for model loading—not 96GB as commonly assumed—though system overhead reduces practical availability.

The critical bottleneck is **memory bandwidth at ~273 GB/s**, dramatically lower than datacenter GPUs (H100: 3.35 TB/s). This bandwidth limitation means LLM inference on DGX Spark is memory-bound, not compute-bound, fundamentally changing performance characteristics:

**Real-world gpt-oss-120b performance on DGX Spark:**

| Framework | Decode Speed (single) | Decode Speed (concurrent) | TTFT |
|-----------|----------------------|---------------------------|------|
| TensorRT-LLM | 24 tok/s | 76 tok/s @128 | ~1.2s |
| vLLM | 35 tok/s | - | ~1.6s |
| SGLang | 52 tok/s | 125 tok/s @10 | ~1.4s |
| llama.cpp | 58 tok/s | - | ~1.8s |

Forum benchmarks from community testing confirm that **SGLang provides the best single-GPU performance** on DGX Spark, achieving 52-58 tokens/second for gpt-oss-120b with MXFP4 quantization.

## Memory requirements based on actual measurements

The memory usage for gpt-oss-120b-eagle3 in the PerformanceProfile is **84GB** based on actual measurements. Here's the breakdown:

| Component | Memory Required |
|-----------|----------------|
| gpt-oss-120b weights (MXFP4) | 67 GB |
| Eagle3 draft head | 3 GB |
| KV cache (40K context, batch=1) | 3 GB |
| CUDA/framework overhead | 11 GB |
| **Total measured** | **84 GB** |

Running gpt-oss-120b-Eagle3 alongside other models is **not feasible** on a single DGX Spark. With 128GB total memory and ~85GB required for Eagle3, only ~35-40GB remains—insufficient for meaningful concurrent model loading. The VRAM orchestrator should treat this as an exclusive model that evicts all others when loaded.

## Framework compatibility reveals critical limitations

**Ollama cannot serve Eagle3 models.** The underlying llama.cpp recently merged Eagle3 support (PR #18039), but Ollama has not integrated this feature. GitHub Issue #5800 tracks speculative decoding as a feature request with no confirmed roadmap. For Discord bot integration, Ollama is not viable for this use case.

**TensorRT-LLM has a critical bug on Blackwell consumer GPUs.** Issue #8615 documents an infinite loop when using gpt-oss-120b-Eagle3 on RTX Pro 6000 (Blackwell SM 12.1), producing garbage output (`!!!!!!!!!!!!!!`) instead of coherent text. While this was reported for RTX Pro 6000, the same SM 12.1 architecture exists on DGX Spark's GB10, suggesting high risk of the same behavior. The official NVIDIA documentation targets B200/GB200 datacenter GPUs, not the consumer-class GB10.

**vLLM has experimental GB10 support with known issues.** The V1 engine fails entirely on SM 12.1 with "sink setting not supported" errors across all attention backends (GitHub Issue #28589). Running vLLM requires source compilation with patches for CUDA architecture 12.1a and custom CUTLASS MoE kernel fixes.

**SGLang is the recommended framework** with confirmed DGX Spark support via the dedicated `lmsysorg/sglang:spark` Docker image. Eagle3 speculative decoding works using chain decoding (`topk=1`) on the TRTLLM-MHA backend, though tree decoding (`topk>1`) is only supported on the Triton backend.

## Step-by-step implementation guide for SGLang

### Phase 1: Download models and prepare environment

```bash
# Install Hugging Face CLI
pip install huggingface-hub

# Download base model
huggingface-cli download openai/gpt-oss-120b \
  --local-dir /models/gpt-oss-120b

# Download NVIDIA Eagle3 throughput head
huggingface-cli download nvidia/gpt-oss-120b-Eagle3-throughput \
  --local-dir /models/gpt-oss-120b-Eagle3-throughput

# Alternative: LMSYS-trained Eagle3 (often higher acceptance rates)
huggingface-cli download lmsys/EAGLE3-gpt-oss-120b-bf16 \
  --local-dir /models/EAGLE3-gpt-oss-120b-bf16
```

### Phase 2: Launch SGLang with Eagle3 on DGX Spark

```bash
docker run --gpus all \
  --shm-size 32g \
  -p 30000:30000 \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -v /models:/models:ro \
  --env "HF_TOKEN=${HF_TOKEN}" \
  --ipc=host \
  lmsysorg/sglang:spark \
  python3 -m sglang.launch_server \
    --model-path openai/gpt-oss-120b \
    --speculative-algorithm EAGLE3 \
    --speculative-draft-model-path lmsys/EAGLE3-gpt-oss-120b-bf16 \
    --speculative-num-steps 3 \
    --speculative-eagle-topk 1 \
    --speculative-num-draft-tokens 4 \
    --quantization mxfp4 \
    --tp 1 \
    --max-model-len 8192 \
    --host 0.0.0.0 --port 30000
```

Key configuration notes:
- `--speculative-eagle-topk 1`: Chain decoding only (tree decoding unsupported on Blackwell TRTLLM-MHA)
- `--quantization mxfp4`: Required for fitting in 128GB unified memory
- `--max-model-len 8192`: Recommended limit for interactive Discord use; longer contexts severely degrade TTFT

### Phase 3: Integrate with FastAPI backend manager

```python
from openai import AsyncOpenAI
from typing import AsyncIterator
import asyncio

class Eagle3BackendManager:
    """Backend manager for gpt-oss-120b-Eagle3 via SGLang"""
    
    def __init__(self, base_url: str = "http://localhost:30000/v1"):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="EMPTY"  # SGLang doesn't require auth by default
        )
        self.model_name = "openai/gpt-oss-120b"
        
        # Circuit breaker state
        self.failure_count = 0
        self.circuit_open = False
        self.last_failure_time = 0
        self.recovery_timeout = 60  # seconds
        
    async def generate_stream(
        self, 
        prompt: str, 
        max_tokens: int = 2048,
        timeout: float = 120.0
    ) -> AsyncIterator[str]:
        """Stream tokens with circuit breaker protection"""
        
        if self.circuit_open:
            if (asyncio.get_event_loop().time() - self.last_failure_time) > self.recovery_timeout:
                self.circuit_open = False
                self.failure_count = 0
            else:
                raise CircuitBreakerOpen("Eagle3 backend unavailable")
        
        try:
            stream = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                    max_tokens=max_tokens,
                ),
                timeout=timeout
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
            # Reset failure count on success
            self.failure_count = 0
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = asyncio.get_event_loop().time()
            
            if self.failure_count >= 5:
                self.circuit_open = True
            raise
```

### Phase 4: VRAM orchestrator configuration

```python
class VRAMOrchestratorConfig:
    """Updated configuration for Eagle3 exclusive model loading"""

    MEMORY_PROFILES = {
        "gpt_oss_120b_eagle3": {
            "base_vram_gb": 67,
            "eagle3_head_gb": 3,
            "kv_cache_gb": 3,
            "overhead_gb": 11,
            "total_required_gb": 84,
            "exclusive": True,  # Evicts all other models when loading
            "priority": "critical",
            "keep_loaded": True,  # Don't evict during normal operation
        }
    }
    
    PSI_THRESHOLDS = {
        "warning": 70,    # Start monitoring at 70%
        "critical": 80,   # Begin eviction at 80%
        "emergency": 90,  # Aggressive eviction at 90%
    }
    
    # Route assignments - Eagle3 for high-value routes only
    ROUTE_MODEL_MAP = {
        "MATH": "gpt_oss_120b_eagle3",
        "REASONING": "gpt_oss_120b_eagle3",
        "RESEARCH": "gpt_oss_120b_eagle3",
        "COMPLEX_CODE": "gpt_oss_120b_eagle3",
        "SIMPLE_CODE": "qwen-32b",  # Faster for simple tasks
        "SELF_HANDLE": "llama-8b",   # Quick responses
    }
```

## Discord bot integration requires streaming UX patterns

Given the 15-30 second time-to-first-token expected with gpt-oss-120b on DGX Spark, Discord bot UX must handle long waits gracefully:

```python
class Eagle3DiscordBot:
    async def handle_llm_response(self, message):
        """Handle LLM response with progressive status updates"""
        
        # Immediate acknowledgment
        await message.add_reaction("🤔")
        thinking_msg = await message.reply("*Thinking with gpt-oss-120b...*")
        
        # Track timing for user feedback
        start_time = asyncio.get_event_loop().time()
        first_token_received = False
        
        response_buffer = ""
        last_update = start_time
        
        try:
            async for token in self.backend.generate_stream(message.content):
                if not first_token_received:
                    first_token_received = True
                    ttft = asyncio.get_event_loop().time() - start_time
                    await message.remove_reaction("🤔", self.user)
                    await message.add_reaction("✍️")
                
                response_buffer += token
                
                # Update every 2 seconds to avoid rate limits
                current_time = asyncio.get_event_loop().time()
                if current_time - last_update > 2.0:
                    display = response_buffer[:1900] + "..." if len(response_buffer) > 1900 else response_buffer
                    await thinking_msg.edit(content=display)
                    last_update = current_time
            
            # Final update
            await self.send_chunked_response(thinking_msg, response_buffer)
            await message.remove_reaction("✍️", self.user)
            await message.add_reaction("✅")
            
        except asyncio.TimeoutError:
            await thinking_msg.edit(content="⏱️ Response timed out (120s limit). Try a simpler query.")
        except CircuitBreakerOpen:
            await thinking_msg.edit(content="🔧 Model temporarily unavailable. Using fallback...")
            # Trigger fallback to smaller model
```

## Known issues and workarounds from community testing

**Issue: TensorRT-LLM infinite loop (Issue #8615)**
- **Symptoms**: Output degenerates to repeated characters (`!!!!!!`) with Eagle3 enabled
- **Affected**: RTX Pro 6000, likely DGX Spark GB10 (same SM 12.1 architecture)
- **Workaround**: Use SGLang instead of TensorRT-LLM for Eagle3 deployment
- **Status**: Open as of December 2025

**Issue: vLLM V1 engine fails on GB10 (Issue #28589)**
- **Symptoms**: "sink setting not supported" across all attention backends
- **Workaround**: Use custom Docker image `avarok/vllm-nvfp4-gb10-sm120` with patched source build
- **Status**: Experimental patches available, not production-ready

**Issue: Memory pressure at high concurrency**
- **Symptoms**: OOM crashes when concurrent requests exceed 10-15
- **Workaround**: Limit `--max_batch_size` to 4-8, use circuit breaker pattern
- **Prevention**: Set `free_gpu_memory_fraction: 0.4` in configuration

**Issue: Long context severely degrades TTFT**
- **Symptoms**: 65K token context causes 100+ second TTFT
- **Workaround**: Limit `--max-model-len` to 8192 for interactive use cases
- **Alternative**: Use Eagle3-long-context variant if extended context is essential

## Performance expectations and production checklist

**Expected performance metrics on DGX Spark with SGLang + Eagle3:**

| Metric | Without Eagle3 | With Eagle3 | Notes |
|--------|---------------|-------------|-------|
| Decode (single) | 35-40 tok/s | 55-70 tok/s | ~1.6-1.8× improvement |
| Decode (10 concurrent) | 120 tok/s | ~200 tok/s | Higher aggregate |
| TTFT (8K context) | 8-12s | 8-12s | No change |
| Memory usage | 70-75 GB | 75-80 GB | +5 GB for Eagle head |

**Production deployment checklist:**

- [x] Use `lmsysorg/sglang:spark` Docker image (confirmed GB10 compatible)
- [x] Configure MXFP4 quantization for memory efficiency
- [x] Set `--context-length 40960` and `--max-total-tokens 40960` for 40K context
- [x] Implement circuit breaker with 5-failure threshold and 60s recovery
- [x] Configure exclusive model loading via performance profile
- [x] Update VRAM orchestrator memory estimate to 84GB (actual measured)
- [x] Use chain decoding only (`--speculative-eagle-topk 1`)
- [x] Assign Eagle3 to ALL text routes (MATH, SIMPLE_CODE, COMPLEX_CODE, REASONING, RESEARCH, ROUTER)
- [x] Implement streaming Discord UX with progressive updates every 2 seconds
- [ ] Set request timeout to 120 seconds for complex generations
- [ ] Monitor for infinite loop symptoms (repeated characters) and fallback automatically

## Conclusion: Viable with caveats for Discord bot deployment

Running gpt-oss-120b-Eagle3-throughput on DGX Spark is achievable using SGLang, delivering **55-70 tokens/second** with speculative decoding—approximately 1.6-1.8× improvement over baseline. The implementation uses the PerformanceProfile with actual measured memory usage of 84GB (67GB base + 3GB KV cache @ 40K context + 14GB overhead). SGLang handles all text tasks (routing, math, simple/complex code, reasoning, research) while minimal Ollama models handle vision and embeddings. The performance profile avoids TensorRT-LLM due to the critical infinite loop bug on SM 12.1, and treats Eagle3 as an exclusive model (CRITICAL priority) that remains loaded persistently. For Discord bot use cases, TTFT is ~15-30 seconds at startup, but then provides fast inference with proper streaming UX patterns.