# DGX Spark Unified Memory: Limits, Multi-Model Hosting, and Crash Prevention

NVIDIA's DGX Spark with Grace-Blackwell GB10 has **128GB unified LPDDR5X memory** shared dynamically between CPU and GPU—but the practical usable memory depends on OS reserves and monitoring methods. The reported "96GB usable" limitation is real but nuanced: `cudaMemGetInfo` underreports available memory because it doesn't account for reclaimable system cache. Actual allocatable memory often exceeds what APIs report. For multi-model LLM hosting, Ollama configuration combined with cgroups-based memory guards provides robust crash prevention, though performance issues with Ollama on DGX Spark make **llama.cpp** the currently recommended inference engine.

## The 96GB Memory Limitation: What's Really Happening

The DGX Spark uses a dynamic Unified Memory Architecture (UMA) where GPU and CPU share the same 128GB LPDDR5X pool—there's no dedicated VRAM. This design eliminates CPU-to-GPU data transfers but creates monitoring complexity.

**Confirmed memory breakdown:**
- **Total installed**: 128GB (119 GiB in binary)
- **System-available**: ~112 GiB after OS/kernel reserves
- **GPU allocation (reported)**: 96GB via cudaMemGetInfo
- **Actual allocatable**: Often higher than 96GB due to dynamic reclamation

NVIDIA's official Known Issues documentation explains: "The `cudaMemGetInfo` API does not account for memory that could potentially be reclaimed from the system's SWAP area and page caches. As a result, reported memory may be smaller than actual allocatable memory."

The workaround is flushing buffer cache before memory-intensive workloads:

```bash
sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'
```

**Model size capabilities (tested):**
| Model | Parameters | Status |
|-------|-----------|--------|
| Llama 3.1 70B | 70B | Works reliably |
| gpt-oss-120B | 120B | Fits entirely, ~120GB with overhead |
| Llama 4 Scout | 109B (17B active) | ~67GB memory |
| Qwen3-235B | 235B | Requires 2× DGX Spark (256GB total) |

NVIDIA officially claims **up to 200B parameters** for single-unit inference and **up to 405B** when two DGX Sparks are connected via ConnectX-7.

## Multi-Model Hosting with Ollama on Unified Memory

Ollama works out-of-box on DGX Spark but requires tuning for multi-model scenarios. The key environment variables control memory behavior:

**Core configuration for multi-model hosting:**
```bash
# /etc/systemd/system/ollama.service.d/override.conf
[Service]
Environment="OLLAMA_MAX_LOADED_MODELS=3"      # Maximum concurrent models
Environment="OLLAMA_NUM_PARALLEL=4"           # Parallel requests per model
Environment="OLLAMA_KEEP_ALIVE=10m"           # Model retention time
Environment="OLLAMA_FLASH_ATTENTION=1"        # Reduces memory usage
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"       # Quantized KV cache
```

**Model loading/unloading controls:**

| Action | Command |
|--------|---------|
| View loaded models | `ollama ps` |
| Preload indefinitely | `curl localhost:11434/api/generate -d '{"model":"llama3.2","keep_alive":-1}'` |
| Force immediate unload | `curl localhost:11434/api/generate -d '{"model":"llama3.2","keep_alive":0}'` |
| Graceful stop | `ollama stop modelname` |

By default, models remain loaded for **5 minutes** after the last request, then unload automatically. When a new model requires memory, idle models are evicted in LRU order. For dynamic routing across multiple models, set `OLLAMA_MAX_LOADED_MODELS` based on your smallest model sizes—three 30GB models or two 50GB models typically work safely within the ~100GB usable envelope.

**Critical performance warning:** Multiple users report Ollama is "extremely slow" on DGX Spark compared to direct llama.cpp usage. One user reported **12 tokens/second** with Ollama versus **60+ tokens/second** with optimized llama.cpp on the same model. NVIDIA and Ollama are actively optimizing, with firmware 580.95.05 recommended for best performance.

## Crash Causes and Prevention Strategies

System crashes on DGX Spark typically manifest as complete freezes (mouse unresponsive, requiring hard reboot) rather than graceful OOM kills.

**Primary crash causes identified:**

1. **Memory mapping (mmap) performance**: Loading large models with mmap takes 1+ minutes and can freeze systems. Solution: use `--no-mmap` flag in llama.cpp
2. **Buffer cache exhaustion**: System doesn't reclaim cache fast enough during rapid model loading
3. **Thermal throttling**: Sustained loads trigger throttling at 100W; spontaneous reboots reported under heavy workloads
4. **Shared memory leaks**: Ollama containers don't properly release shared memory segments after stopping

**Preventive measures:**

```bash
# Before loading large models
sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'

# Disable memory mapping for model loading (llama.cpp)
./llama-server --model model.gguf --no-mmap

# Kill shared memory after stopping Ollama containers
ipcs -m | grep nobody | awk '{print $2}' | xargs -I {} ipcrm -m {}
```

**Key observation:** nvidia-smi showing "Memory-Usage: Not Supported" is **expected behavior** on unified memory systems—there's no dedicated framebuffer to report. This breaks many third-party monitoring tools (HAMi, GPU Operator for Kubernetes) that expect nvidia-smi memory values.

## Implementing Memory Guards and Soft Limits

Since nvidia-smi doesn't work for memory monitoring, use Linux-native tools and cgroups for protection.

**System monitoring for unified memory:**
```bash
# Real-time memory and pressure monitoring
watch -n 1 'free -h && cat /proc/pressure/memory'

# PSI (Pressure Stall Information) - early warning system
cat /proc/pressure/memory
# some avg10=0.00 avg60=0.00 avg300=0.00 total=123456
# full avg10=0.00 avg60=0.00 avg300=0.00 total=78901
```

**Recommended thresholds for LLM services:**

| Metric | Warning | Critical |
|--------|---------|----------|
| PSI some avg10 | >20% | >50% |
| PSI full avg10 | >5% | >15% |
| MemAvailable | <15% | <10% |

**systemd-based memory protection (recommended):**
```ini
# /etc/systemd/system/llm-service.service
[Service]
MemoryAccounting=yes
MemoryMin=8G                      # Guaranteed minimum
MemoryLow=60G                     # Protected from reclaim
MemoryHigh=100G                   # Soft limit (throttling starts)
MemoryMax=110G                    # Hard limit (OOM kill)
MemorySwapMax=0                   # Disable swap (critical for LLM performance)

OOMPolicy=stop                    # Stop service on OOM
OOMScoreAdjust=-500               # Protect from OOM killer

ManagedOOMMemoryPressure=kill
ManagedOOMMemoryPressureLimit=80%
```

**Proactive memory watchdog script:**
```bash
#!/bin/bash
while true; do
    MEM_USED=$(free | awk '/Mem:/ {printf "%.0f", $3/$2 * 100}')
    if (( MEM_USED > 85 )); then
        echo "Memory at ${MEM_USED}% - triggering graceful degradation"
        ollama stop $(ollama ps | tail -1 | awk '{print $1}')  # Unload oldest model
    fi
    sleep 10
done
```

For additional protection, install **earlyoom** which proactively kills processes before the system becomes unresponsive:
```bash
sudo apt install earlyoom
# Configure: act when <10% memory available
echo 'EARLYOOM_ARGS="-m 10 -s 90"' | sudo tee /etc/default/earlyoom
```

## NUMA and Architecture-Specific Optimizations

The GB10 Superchip has a unique architecture: the Blackwell GPU accesses LPDDR5X through the MediaTek CPU die's memory controllers via NVLink-C2C (600 GB/s bidirectional). This creates NUMA-like behavior that benefits from specific tuning.

**Disable AutoNUMA for GPU workloads:**
```bash
echo 0 > /proc/sys/kernel/numa_balancing
```

**Memory bandwidth is the primary bottleneck** at 273 GB/s—roughly 2× slower than RTX 5070 and 6× slower than RTX 5090. This impacts decode speed (memory-bound) more than prefill (compute-bound). Expect excellent prompt processing but modest token generation rates on large models.

**Kernel tuning for LLM workloads:**
```bash
# /etc/sysctl.d/99-llm.conf
vm.swappiness = 10               # Minimize swapping
vm.vfs_cache_pressure = 50       # Reduce cache pressure
vm.overcommit_memory = 0         # Conservative overcommit
```

## Practical Configuration Summary

For a production multi-model setup on DGX Spark:

1. **Use llama.cpp instead of Ollama** for inference until Ollama optimization is complete
2. **Set memory limits** via systemd (MemoryHigh=100G, MemoryMax=110G)
3. **Flush cache** before loading large models: `sync; echo 3 > /proc/sys/vm/drop_caches`
4. **Disable mmap** when loading models: `--no-mmap` flag
5. **Monitor PSI** for early warning of memory pressure
6. **Install earlyoom** as a safety net against system freezes
7. **Limit concurrent models** based on size: realistically 2-3 models totaling ~100GB
8. **Expect ~96GB usable** for GPU workloads after OS reserves, though actual allocation may exceed this

## Conclusion

DGX Spark's unified memory architecture offers significant advantages for large model hosting—200B parameters on a $4000 desktop device—but requires understanding its unique characteristics. The "96GB limitation" is an artifact of conservative reporting by `cudaMemGetInfo` rather than a hard constraint. System crashes stem primarily from mmap performance issues and thermal throttling rather than memory exhaustion. Implementing cgroups-based memory guards, PSI monitoring, and cache management transforms DGX Spark from a potentially unstable platform into a reliable multi-model inference server. The memory bandwidth constraint (273 GB/s) makes it excellent for large context windows and batch processing but limits decode speed compared to discrete GPUs—design your workloads accordingly.

---

## References

- [NVIDIA DGX Spark Official Documentation](https://docs.nvidia.com/dgx/dgx-spark/)
- [Ollama Blog: NVIDIA DGX Spark](https://ollama.com/blog/nvidia-spark)
- [NVIDIA DGX Spark Porting Guide](https://docs.nvidia.com/dgx/dgx-spark-porting-guide/)
- [NVIDIA Developer Forums: DGX Spark / GB10](https://forums.developer.nvidia.com/c/accelerated-computing/dgx-spark-gb10/)
- [LMSYS DGX Spark Review](https://lmsys.org/blog/2025-10-13-nvidia-dgx-spark/)