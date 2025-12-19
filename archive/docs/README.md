# Archived Documentation

This directory contains outdated or superseded documentation that is preserved for historical reference.

## Contents

### local-llm-guide.md

**Status**: Outdated (as of December 2025)

**Original Purpose**: Guide for setting up local LLM models with Ollama, including model selection, performance optimization, and hardware recommendations.

**Why Archived**:
- Reflects an earlier system architecture that has since evolved
- Model recommendations and routing system have changed significantly
- New routing system with 6 specialized routes (MATH, SIMPLE_CODE, COMPLEX_CODE, REASONING, RESEARCH, SELF_HANDLE) is not reflected
- Current model configurations are documented in the main [README.md](../../README.md)

**Current Documentation**:
- For user setup: See [README.md](../../README.md)
- For technical details: See [TECHNICAL.md](../../TECHNICAL.md)
- For model configuration: See [fastapi-service/app/config.py](../../fastapi-service/app/config.py)
- For model tool support: See [fastapi-service/MODEL-TOOL-SUPPORT.md](../../fastapi-service/MODEL-TOOL-SUPPORT.md)

## Viewing Archived Documents

These documents are preserved for reference but should not be used for current setup or configuration. They may contain outdated information about:
- Model selection criteria
- Routing logic (old system used different models/routes)
- Configuration options that no longer exist
- Performance characteristics of deprecated models

**Always refer to current documentation** in the root directory for up-to-date information.

---

**Note**: If you find useful content in these archived documents that should be in current documentation, please open an issue or pull request.
