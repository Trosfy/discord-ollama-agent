# SGLang High-Performance LLM Backend

Self-contained SGLang server for gpt-oss-120b with EAGLE3 speculative decoding.

## Requirements

- **GPU Memory**: ~84GB VRAM
- **System Memory**: ~50GB swap (enabled during startup only)
- **Container Runtime**: NVIDIA Docker runtime

## Usage

```bash
# Start SGLang (handles swap/earlyoom/memory management)
./scripts/model_management/sglang/start.sh

# Check status
./scripts/model_management/sglang/status.sh

# Stop SGLang
./scripts/model_management/sglang/stop.sh
```

## What Start Script Does

1. **Enables swap** - Required for MoE weight shuffling during startup
2. **Disables earlyoom** - Prevents OOM killer during high memory usage
3. **Flushes buffer cache** - Maximizes available memory
4. **Starts container** - Uses docker-compose.yml in this directory
5. **Monitors health** - Waits for model to load (~5-10 minutes)
6. **Re-enables earlyoom** - Restores OOM protection
7. **Disables swap** - Prevents thermal issues after model is loaded

## Startup Time

MoE weight shuffling takes ~5-10 minutes on first start. The script monitors
progress and waits for the healthcheck to pass before completing.

## Endpoint

Once healthy, SGLang is available at: `http://localhost:30000`

Compatible with OpenAI API format:
- `POST /v1/chat/completions`
- `GET /v1/models`

## Docker Compose

This directory contains a self-contained `docker-compose.yml` that defines
the SGLang service. It uses the `trollama-network` to communicate with
other containers in the project.

## Troubleshooting

```bash
# View container logs
docker logs trollama-sglang

# Check if container is running
docker ps --filter "name=trollama-sglang"

# Force stop and remove
docker stop trollama-sglang && docker rm trollama-sglang

# Restart
./scripts/model_management/sglang/stop.sh
./scripts/model_management/sglang/start.sh
```

## Notes

- Container name: `trollama-sglang`
- Port: 30000
- Model: `openai/gpt-oss-120b` with EAGLE3 speculative decoding
- ~1.6-1.8x speedup compared to standard inference
