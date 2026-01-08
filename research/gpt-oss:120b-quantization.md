# SGLang MXFP4 quantization: The slowdown isn't what you think

**The gpt-oss-120b model is already natively quantized in MXFP4 format**, eliminating concerns about runtime quantization. However, the **4-5 minute container startup time** stems from a different culprit: SGLang's MoE weight shuffling operation for the FlashInfer MXFP4 kernel. This weight rearrangement occurs fresh on every launch with **no caching mechanism currently available**, making it the primary bottleneck for deployment workflows requiring frequent restarts.

## Native MXFP4 means no runtime quantization occurs

OpenAI released gpt-oss-120b with MXFP4 quantization baked in during training—a quantization-aware training (QAT) approach. The model's `config.json` contains a `quantization_config` specifying `quant_method: mxfp4`, with MoE expert weights stored as packed FP4 values (two values per uint8) alongside E8M0 block scales. Non-MoE components including attention layers, router weights, embeddings, and the language model head remain in **BF16 precision**.

The storage structure uses safetensors format across 14 shards totaling **~196 GB**. Each quantized tensor is split into `tensor.blocks` (packed FP4 values) and `tensor.scales` (per-block scaling factors), enabling efficient loading without decompression overhead. This hybrid approach—MXFP4 for the 90%+ of parameters in MoE experts, BF16 for everything else—was specifically designed to fit the 120B model on a single H100 80GB GPU while preserving accuracy within **≤0.3% degradation**.

## What SGLang's `--quantization mxfp4` flag actually controls

For properly formatted MXFP4 checkpoints like gpt-oss-120b, **you don't need to specify `--quantization mxfp4` at all**. SGLang auto-detects the quantization method from the checkpoint's configuration and loads pre-quantized weights directly. The flag exists primarily for edge cases where format detection fails or when applying MXFP4 to models not originally quantized in that format.

The correct launch command is simply:
```bash
python3 -m sglang.launch_server --model openai/gpt-oss-120b --tp 2
```

What consumes startup time is the **MoE weight shuffling operation** that rearranges weights for the FlashInfer MXFP4 MoE kernel. GitHub issue #9094 documents this taking **4-5 minutes for gpt-oss-120b**—the log message "Shuffling MoE weights for FlashInfer MXFP4 MoE kernel" marks this phase. This is architectural preparation, not quantization conversion.

## Pre-quantization options and their limitations

Since gpt-oss-120b ships pre-quantized, the question becomes whether you can pre-shuffle the weights. Currently, **no mechanism exists to cache the shuffled weight layout**. The operations that occur at startup include:

- Model weight loading from disk (~1-2 minutes depending on storage)
- Weight sharding across tensor parallel ranks
- **MoE weight shuffling for FlashInfer kernel (4-5 minutes)**
- CUDA graph capture (~30-60 seconds)

For other models not natively MXFP4, **AMD Quark** provides offline quantization:
```bash
python3 quantize_quark.py \
    --model_dir meta-llama/Llama-3.3-70B-Instruct \
    --quant_scheme w_mxfp4_a_mxfp4 \
    --output_dir ./Llama-MXFP4 \
    --num_calib_data 512
```

Intel AutoRound and NVIDIA's TensorRT Model Optimizer also support MXFP4, though ecosystem compatibility varies. Pre-quantized AMD models like `amd/DeepSeek-R1-0528-MXFP4-Preview` demonstrate the workflow but face the same shuffling overhead in SGLang.

## Available workarounds for faster container launches

The most effective strategies target different parts of the startup pipeline:

**Skip server warmup** reduces CUDA graph capture time by 30-60 seconds but doesn't affect shuffling:
```bash
python3 -m sglang.launch_server --model openai/gpt-oss-120b --tp 2 --skip-server-warmup
```

**Alternative kernel backend** may have different startup characteristics—the Triton kernel backend bypasses FlashInfer-specific shuffling:
```bash
python3 -m sglang.launch_server --model openai/gpt-oss-120b \
    --moe-runner-backend triton_kernel --tp 2
```

**Persistent server architecture** is the most practical solution: keep the SGLang server running continuously rather than starting/stopping containers. For Kubernetes deployments, this means using persistent pods rather than job-based scaling.

**Storage optimization** provides marginal gains—safetensors format loads **76× faster on CPU, 2× faster on GPU** than pickle-based pytorch_model.bin, and gpt-oss-120b already uses safetensors. NVMe storage and sufficient system RAM for caching reduce I/O time but don't impact shuffling.

## No pre-shuffled checkpoints exist today

Community quantized versions don't solve the shuffling problem:

| Repository | Format | Shuffling Required |
|------------|--------|-------------------|
| openai/gpt-oss-120b | Native MXFP4 | Yes (FlashInfer) |
| unsloth/gpt-oss-120b-GGUF | GGUF Q4-Q8 | N/A (different runtime) |
| mlx-community/gpt-oss-120b-MXFP4-Q4 | MLX | N/A (Apple Silicon) |

The GGUF versions from Unsloth (~62-65 GB) work with llama.cpp without shuffling overhead but sacrifice MXFP4's native hardware acceleration on H100/Blackwell GPUs. MLX versions target Apple Silicon exclusively.

SGLang's ModelOpt integration offers `--modelopt-checkpoint-save-path` and `--modelopt-checkpoint-restore-path` for saving/restoring quantized checkpoints, but **these flags don't apply to MXFP4**—they're designed for NVIDIA's ModelOpt FP8/INT8 workflows only.

## Hardware and format considerations

**Native MXFP4 acceleration** requires NVIDIA Blackwell (B100/B200, RTX 50-series) or AMD MI355X. On H100/H200, computation runs in emulation mode with dequantization to BF16. The shuffling operation itself runs on GPU regardless of architecture.

Safetensors versus pytorch_model.bin affects initial load time but not the shuffling phase—once weights are in GPU memory, the format doesn't matter. For the 196 GB gpt-oss-120b checkpoint, safetensors' memory-mapped loading reduces peak RAM usage during initial transfer.

## Conclusion

The startup delay for gpt-oss-120b in SGLang comes from **MoE weight shuffling, not quantization**—the model arrives pre-quantized in MXFP4 format. With no caching mechanism for shuffled weights and no pre-shuffled checkpoints available, the practical solutions are: switch to `triton_kernel` backend if FlashInfer-specific optimizations aren't critical, architect your deployment for persistent servers rather than frequent restarts, or monitor GitHub issue #9094 for potential upstream improvements to the shuffling implementation. The 4-5 minute startup overhead is currently an architectural reality of the FlashInfer MXFP4 MoE kernel integration.