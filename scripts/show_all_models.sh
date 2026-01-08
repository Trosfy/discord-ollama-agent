#!/bin/bash
# Show modelfile for all Ollama models (without LICENSE sections)

echo "=========================================="
echo "Ollama Model Configurations"
echo "=========================================="
echo ""

# Get list of models (skip header line)
models=$(ollama list | tail -n +2 | awk '{print $1}')

for model in $models; do
    echo "==================== $model ===================="
    echo ""

    # Show modelfile and filter out LICENSE section
    ollama show "$model" --modelfile | awk '
        /^LICENSE / { in_license=1; next }
        /^[A-Z]+ / && in_license { in_license=0 }
        !in_license { print }
    '

    echo ""
    echo ""
done

echo "=========================================="
echo "All model configurations displayed"
echo "=========================================="
