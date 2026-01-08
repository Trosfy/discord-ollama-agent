# NVFP4 Quantization: NVIDIA's Proprietary 4-Bit Format for Blackwell GPUs

**NVFP4 is a genuine NVIDIA-proprietary quantization format—not just rebranded MXFP4.** It uses smaller 16-element blocks with E4M3 scaling (vs. MXFP4's 32-element blocks and E8M0 scaling), delivering ~88% lower quantization error. All major runtimes now support it: TensorRT-LLM (native), SGLang (via `modelopt_fp4`), and vLLM (v0.12+). The DGX Spark GB10 provides native FP4 tensor core acceleration at **1 PFLOP sparse throughput**, and with **63+ NVFP4 models** on HuggingFace including massive MoE architectures, this format is growing rapidly—warranting infrastructure investment.

---

## NVFP4 technical specification reveals key differences from MXFP4

NVFP4 employs a **two-level hierarchical scaling architecture** that fundamentally distinguishes it from other 4-bit formats. The base 4-bit value uses E2M1 encoding (1 sign, 2 exponent, 1 mantissa bits) representing values from **-6 to +6**. The critical innovation lies in the micro-block structure:

| Feature | NVFP4 (NVIDIA) | MXFP4 (OCP Standard) |
|---------|----------------|----------------------|
| **Block Size** | 16 elements | 32 elements |
| **Scale Format** | E4M3 FP8 (fractional) | E8M0 (power-of-2 only) |
| **Per-Tensor Scale** | FP32 (required) | Not used |
| **Quantization Error (MSE)** | ~0.08 | ~0.72 |
| **Bits per Value** | ~4.5 effective | ~4.25 effective |
| **Standardization** | NVIDIA proprietary | OCP open standard |

The E4M3 scale format enables **fractional scaling precision**, while MXFP4's E8M0 restricts to power-of-two multiples. Combined with smaller blocks, NVFP4 achieves finer-grained representation that translates to measurable accuracy improvements—**~5% higher MMLU scores** on Llama 3.3 70B compared to MXFP4.

**Critical finding: MXFP4 and NVFP4 checkpoints are NOT interchangeable.** Models quantized to NVFP4 cannot be loaded by runtimes expecting MXFP4, and vice versa. This means the existing SGLang MXFP4 infrastructure (gpt-oss-120b-eagle3) **cannot directly load NVFP4 models**.

---

## Runtime support spans all major inference frameworks

All four target runtimes now support NVFP4, with TensorRT-LLM providing the most mature implementation:

### TensorRT-LLM (Primary, Native Support)
```bash
# Docker launch
docker run --rm -it --ipc host --gpus all -p 8000:8000 \
  nvcr.io/nvidia/tensorrt-llm/release:1.2.0rc6

# Serve NVFP4 model with OpenAI-compatible API
trtllm-serve "nvidia/Llama-3.3-70B-Instruct-FP4" --backend pytorch --tp_size 8
```
- **API**: OpenAI-compatible (`/v1/chat/completions`)
- **Requirements**: CUDA 12.9+, Driver 570.172+, Blackwell SM100/SM120

### SGLang (Supported via modelopt_fp4)
```bash
python -m sglang.launch_server \
  --model-path nvidia/Llama-3.3-70B-Instruct-FP4 \
  --quantization modelopt_fp4 \
  --tp 8 \
  --attention-backend flashinfer
```
- **API**: OpenAI-compatible (port 30000)
- **Key distinction**: `modelopt_fp4` = NVFP4, `mxfp4` = MXFP4—different flags for different formats
- **Requirements**: SGLang v0.5.0+, Blackwell GPUs

### vLLM (Early Support v0.12+)
```bash
vllm serve nvidia/Llama-4-Scout-17B-16E-Instruct-FP4 \
  --tensor-parallel-size 2 \
  --kv-cache-dtype fp8
```
- **API**: OpenAI-compatible
- **Quantization tool**: LLM Compressor with `scheme="NVFP4"`

### NVIDIA NIM (Container-Based)
Pre-packaged containers with automatic profile selection. NVFP4 profiles available for Blackwell deployments.

---

## DGX Spark GB10 delivers native FP4 hardware acceleration

The GB10 specifications confirm full Blackwell FP4 capabilities:

| Component | Specification |
|-----------|---------------|
| **GPU** | NVIDIA GB10 (Blackwell) |
| **CUDA Compute Capability** | **SM 12.1 (sm_121)** |
| **Total Unified Memory** | 128GB LPDDR5x-9400 |
| **Memory Bandwidth** | 273-301 GB/s |
| **Tensor Cores** | 192 (5th Generation) |
| **FP4 Performance** | **1 PFLOP sparse, ~500 TFLOPS dense** |
| **FP8 Performance** | ~500 TFLOPS |
| **FP32 Performance** | 31 TFLOPS |
| **TDP** | 140W (SoC), 240W peak |
| **CPU** | NVIDIA Grace, 20-core ARM v9.2 |
| **Supported Precision** | FP4, FP6, FP8, INT8, FP16, BF16, TF32, FP32, FP64 |

**GB10's 5th-generation Tensor Cores include native FP4 instructions** (`tcgen05.mma`), providing hardware-accelerated NVFP4 inference without software emulation overhead. On pre-Blackwell GPUs (Ampere, Hopper), FP4 operations are emulated through higher-precision kernels with **no latency advantage over BF16**. On Blackwell, NVFP4 workloads achieve measurable speedups—approximately **2x faster prefill** in benchmark scenarios.

The memory bandwidth constraint (**273 GB/s vs. B200's ~8 TB/s**) limits absolute throughput, but the FP4 tensor cores maximize efficiency within that bandwidth envelope.

---

## HuggingFace hosts 63+ NVFP4 models across diverse architectures

NVFP4 model availability has grown significantly:

| Category | Parameter Range | Examples |
|----------|-----------------|----------|
| **Small** | 0.6B-8B | Qwen3-0.6B, Qwen3-8B, Phi-4-multimodal |
| **Medium** | 14B-32B | Qwen3-14B, Mistral-Small-24B, Qwen3-32B |
| **Large Dense** | 70B-123B | Llama-3.3-70B, Behemoth-X-123B, gpt-oss-120B |
| **Large MoE** | 80B-1T total | Qwen3-30B-A3B, DeepSeek-R1 (685B), Kimi-K2 (1T) |

**Publisher distribution**: ~40% NVIDIA, ~25% RedHatAI, ~35% community. Both NVIDIA and RedHatAI actively publish NVFP4 checkpoints, with the RedHatAI collection providing vLLM-optimized versions via LLM Compressor. Model families represented include **Qwen3, Llama, DeepSeek, Mistral, Phi, and Kimi**.

The format shows clear growth indicators: enterprise adoption (RedHatAI), active tooling development (TensorRT Model Optimizer, LLM Compressor), and models uploaded as recently as December 2025. NVFP4 is **not niche**—it's becoming the standard 4-bit format for Blackwell deployments.

---

## Qwen3-Next-80B-A3B fits within 128GB unified memory

The Qwen3-Next-80B-A3B model uses an extreme MoE architecture:

| Specification | Value |
|---------------|-------|
| **Total Parameters** | 80B |
| **Active Parameters (A3B)** | ~3B per token |
| **Architecture** | MoE with 512 experts, 10 activated |
| **Context Length** | 256K native, 1M with YaRN |
| **Layers** | 48 |
| **Hidden Dimension** | 2048 |
| **NVFP4 Memory Footprint** | **~40-48GB** |

This model comfortably fits within the DGX Spark's **128GB unified memory**, leaving substantial headroom for KV cache at extended context lengths. The "A3B" designation indicates only **3B parameters activate per token**, providing inference efficiency comparable to a 3B dense model despite 80B total parameters.

**Deployment options**:
- **RedHatAI/Qwen3-Next-80B-A3B-Instruct-NVFP4**: Optimized for vLLM
- **nvidia/Qwen3-Next-80B-A3B-Thinking-NVFP4**: Optimized for TensorRT-LLM

Both require `transformers>=4.57.0` (from main branch) due to the new Qwen3-Next architecture with hybrid Gated DeltaNet + Gated Attention.

---

## Integration recommendation: Extend SGLang with NVFP4 support

Based on the research findings, here are the decision points:

### Primary Runtime for NVFP4
**Recommendation: SGLang with `modelopt_fp4`**

SGLang already integrates with your Trollama infrastructure and supports NVFP4 via the `--quantization modelopt_fp4` flag. This requires **no new backend implementation**—only configuration changes:

```bash
# Current MXFP4 setup
python -m sglang.launch_server --model-path gpt-oss-120b-eagle3 --tp 8

# New NVFP4 setup (different model, different flag)
python -m sglang.launch_server \
  --model-path nvidia/Llama-3.3-70B-Instruct-FP4 \
  --quantization modelopt_fp4 \
  --tp 8
```

### Backend Implementation Scope
**Extend existing SGLang backend**, not new backend. The key changes needed:

1. Add `quantization` parameter to SGLang backend configuration
2. Support switching between `mxfp4` and `modelopt_fp4` quantization modes
3. Validate model format compatibility before loading

TensorRT-LLM remains a valid alternative for maximum performance, but requires implementing the stub backend manager—more significant scope.

### NVFP4 vs MXFP4 Infrastructure
**NVFP4 requires separate model checkpoints but can share the SGLang runtime.** You cannot load NVFP4 models with MXFP4 configuration, but the same SGLang backend handles both formats with different `--quantization` flags.

### Go/No-Go on NVFP4 Investment
**GO**: NVFP4 is worth the integration effort based on:

- **Hardware alignment**: GB10 has native FP4 tensor cores; NVFP4 extracts maximum value
- **Model availability**: 63+ models including DeepSeek-R1, Llama 4, Qwen3-Next, Kimi K2
- **Accuracy advantage**: ~5% higher benchmark scores vs MXFP4
- **Format trajectory**: Growing rapidly with NVIDIA and enterprise support
- **Low integration cost**: SGLang already supports it—configuration change only

---

## Conclusion: NVFP4 maximizes DGX Spark capabilities

NVFP4 represents a genuine technical advancement over MXFP4 with measurable accuracy benefits and native Blackwell hardware acceleration. The format is neither marketing rebranding nor a dead-end—it's actively growing with 63+ models and support across all major inference frameworks.

For the Trollama infrastructure on DGX Spark GB10, the optimal path forward is **extending the existing SGLang backend configuration** to support NVFP4 models via the `modelopt_fp4` quantization flag. This provides access to NVIDIA's NVFP4 model catalog (including the target Qwen3-Next-80B-A3B at ~45GB footprint) while minimizing integration scope.

The key insight: **NVFP4 and MXFP4 are distinct formats requiring separate model checkpoints**, but they share runtime infrastructure. Your existing SGLang investment transfers directly—only the model loading configuration changes.