"""Text and code file extractor."""
import logging
from pathlib import Path
from typing import List

from .interface import IContentExtractor, ExtractionResult

logger = logging.getLogger(__name__)


class TextExtractor:
    """Extract text content from plain text and code files.

    Handles:
    - Plain text files (txt, md, rst)
    - Code files (py, js, ts, java, cpp, etc.)
    - Config files (yaml, yml, json, toml, ini)
    - Shell scripts (sh, bash, zsh)
    """

    # Supported MIME types
    MIMETYPES = [
        # Plain text
        "text/plain",
        "text/markdown",
        "text/x-rst",
        # Code
        "text/x-python",
        "text/x-python-script",
        "application/x-python-code",
        "text/javascript",
        "application/javascript",
        "text/typescript",
        "text/x-java-source",
        "text/x-c",
        "text/x-c++",
        "text/x-go",
        "text/x-rust",
        "text/x-ruby",
        "text/x-php",
        "text/x-shellscript",
        # Config
        "text/yaml",
        "application/x-yaml",
        "application/json",
        "text/json",
        "application/toml",
        "text/x-ini",
        # Fallback for text/*
        "text/*",
    ]

    # Common text file extensions (fallback detection)
    TEXT_EXTENSIONS = {
        # Plain text
        "txt", "md", "rst", "text",
        # Code
        "py", "js", "ts", "jsx", "tsx", "java", "c", "cpp", "h", "hpp",
        "go", "rs", "rb", "php", "swift", "kt", "scala", "cs", "vb",
        "lua", "r", "pl", "pm", "sh", "bash", "zsh", "fish",
        # Config
        "yaml", "yml", "json", "toml", "ini", "cfg", "conf",
        # Web
        "html", "htm", "css", "scss", "sass", "less",
        # Other
        "sql", "graphql", "proto", "dockerfile", "makefile",
    }

    @property
    def supported_mimetypes(self) -> List[str]:
        return self.MIMETYPES

    async def extract(self, file_path: str, mimetype: str) -> ExtractionResult:
        """Extract text from file.

        Args:
            file_path: Path to the file.
            mimetype: MIME type of the file.

        Returns:
            ExtractionResult with text content.
        """
        path = Path(file_path)

        if not path.exists():
            return ExtractionResult(
                text="",
                extractor_name="TextExtractor",
                status="error",
                error_message=f"File not found: {file_path}",
            )

        # Check if it's likely a text file
        ext = path.suffix.lstrip(".").lower()
        if ext not in self.TEXT_EXTENSIONS and not mimetype.startswith("text/"):
            return ExtractionResult(
                text="",
                extractor_name="TextExtractor",
                status="error",
                error_message=f"Not a recognized text file: {file_path}",
            )

        try:
            # Try common encodings
            for encoding in ["utf-8", "latin-1", "cp1252"]:
                try:
                    content = path.read_text(encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # Fallback to binary read with error handling
                content = path.read_bytes().decode("utf-8", errors="replace")

            # Basic stats
            lines = content.count("\n") + 1
            word_count = len(content.split())

            return ExtractionResult(
                text=content,
                extractor_name="TextExtractor",
                status="success",
                metadata={
                    "lines": lines,
                    "word_count": word_count,
                    "char_count": len(content),
                    "extension": ext,
                },
            )

        except Exception as e:
            logger.error(f"Failed to extract text from {file_path}: {e}")
            return ExtractionResult(
                text="",
                extractor_name="TextExtractor",
                status="error",
                error_message=str(e),
            )
