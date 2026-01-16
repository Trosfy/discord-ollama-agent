"""Content sanitizer for extracted artifacts.

Strips preamble/postamble from extracted content.
Handles the "dumb agent" problem:
- "Hi! Here's your file:" → removed
- "Hope this helps!" → removed
- Actual code content → preserved
"""
import re
from typing import Optional


class ContentSanitizer:
    """Strip preamble/postamble from extracted content.

    Handles the "dumb agent" problem:
    - "Hi! Here's your file:" → removed
    - "Hope this helps!" → removed
    - Actual code content → preserved

    Example:
        sanitizer = ContentSanitizer()

        # Input: "Here's the code:\\n```python\\nprint('hello')\\n```\\nHope this helps!"
        # Output: "print('hello')"
        clean = sanitizer.sanitize(content, "code")
    """

    # Common preamble patterns
    PREAMBLE_PATTERNS = [
        r"^(?:Hi!?|Hello!?|Sure!?|Here(?:'s| is))[^\n]*\n+",
        r"^(?:I've created|I have created|Here's the)[^\n]*\n+",
        r"^(?:Certainly!?|Of course!?|Absolutely!?)[^\n]*\n+",
        r"^(?:Below is|The following is|This is)[^\n]*\n+",
    ]

    # Common postamble patterns
    POSTAMBLE_PATTERNS = [
        r"\n+(?:Hope this helps|Let me know|Feel free)[^\n]*$",
        r"\n+(?:Is there anything else)[^\n]*$",
        r"\n+(?:If you have any questions)[^\n]*$",
        r"\n+(?:Happy coding|Good luck)[^\n]*!?$",
    ]

    def sanitize(
        self,
        content: str,
        artifact_type: str,
        preserve_code_blocks: bool = True,
    ) -> str:
        """Remove conversational fluff from content.

        Args:
            content: Content to sanitize.
            artifact_type: Type of artifact ("code", "text", "data").
            preserve_code_blocks: Extract content from code blocks.

        Returns:
            Sanitized content.
        """
        result = content.strip()

        # For code, try to extract from code block first
        if artifact_type == "code" and preserve_code_blocks:
            code_match = re.search(
                r'```(?:\w+)?\n(.*?)```',
                result,
                re.DOTALL
            )
            if code_match:
                return code_match.group(1).strip()

        # Strip preamble patterns
        for pattern in self.PREAMBLE_PATTERNS:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)

        # Strip postamble patterns
        for pattern in self.POSTAMBLE_PATTERNS:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)

        # Strip standalone code fences if present
        result = re.sub(r'^```\w*\n', '', result)
        result = re.sub(r'\n```$', '', result)

        return result.strip()

    def extract_code_blocks(self, content: str) -> list:
        """Extract all code blocks from content.

        Args:
            content: Content with code blocks.

        Returns:
            List of (language, code) tuples.
        """
        pattern = r'```(\w*)\n(.*?)```'
        matches = re.findall(pattern, content, re.DOTALL)
        return [(lang or "text", code.strip()) for lang, code in matches]

    def infer_artifact_type(self, content: str, filename: Optional[str] = None) -> str:
        """Infer artifact type from content and filename.

        Args:
            content: Content to analyze.
            filename: Optional filename for extension-based detection.

        Returns:
            Artifact type ("code", "text", "data").
        """
        if filename:
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            code_exts = {"py", "js", "ts", "java", "cpp", "c", "go", "rs", "rb", "php", "sh"}
            data_exts = {"json", "yaml", "yml", "csv", "xml", "toml"}

            if ext in code_exts:
                return "code"
            elif ext in data_exts:
                return "data"

        # Check content for code patterns
        code_patterns = [
            r'\bdef\s+\w+\s*\(',  # Python function
            r'\bfunction\s+\w+\s*\(',  # JavaScript function
            r'\bclass\s+\w+',  # Class definition
            r'\bimport\s+',  # Import statement
            r'\bfrom\s+\w+\s+import',  # Python import
            r'\bconst\s+\w+\s*=',  # JavaScript const
            r'\blet\s+\w+\s*=',  # JavaScript let
        ]

        for pattern in code_patterns:
            if re.search(pattern, content):
                return "code"

        return "text"
