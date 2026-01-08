"""Unit tests for TextExtractor."""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile

from app.services.extractors.text_extractor import TextExtractor


@pytest.fixture
def text_extractor():
    """Create TextExtractor instance."""
    return TextExtractor()


@pytest.fixture
def temp_text_file():
    """Create temporary test text file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is test text content.\nLine 2.\nLine 3.")
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_python_file():
    """Create temporary test Python file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def hello():\n    print('Hello, world!')\n")
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_json_file():
    """Create temporary test JSON file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"name": "test", "value": 123}')
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


class TestTextExtractor:
    """Test cases for TextExtractor."""

    def test_supported_extensions(self, text_extractor):
        """Test that TextExtractor reports correct supported extensions."""
        extensions = text_extractor.supported_extensions()

        assert isinstance(extensions, set)

        # Text files
        assert '.txt' in extensions
        assert '.md' in extensions
        assert '.csv' in extensions
        assert '.log' in extensions

        # Code files
        assert '.py' in extensions
        assert '.js' in extensions
        assert '.ts' in extensions
        assert '.tsx' in extensions
        assert '.jsx' in extensions

        # Config files
        assert '.json' in extensions
        assert '.yaml' in extensions
        assert '.yml' in extensions
        assert '.toml' in extensions

        # Markup files
        assert '.html' in extensions
        assert '.xml' in extensions
        assert '.css' in extensions

        # Database files
        assert '.sql' in extensions

        # Shell scripts
        assert '.sh' in extensions
        assert '.bash' in extensions

        # Other languages
        assert '.rs' in extensions
        assert '.go' in extensions
        assert '.c' in extensions
        assert '.cpp' in extensions
        assert '.h' in extensions

        # All should have leading dots
        for ext in extensions:
            assert ext.startswith('.')

    def test_supported_mime_types(self, text_extractor):
        """Test that TextExtractor reports correct MIME types."""
        mime_types = text_extractor.supported_mime_types()

        assert isinstance(mime_types, set)
        assert 'text/plain' in mime_types
        assert 'text/markdown' in mime_types
        assert 'text/csv' in mime_types
        assert 'text/html' in mime_types
        assert 'text/xml' in mime_types
        assert 'text/css' in mime_types
        assert 'application/json' in mime_types
        assert 'application/javascript' in mime_types
        assert 'application/x-yaml' in mime_types

    @pytest.mark.asyncio
    async def test_extract_text_file_success(self, text_extractor, temp_text_file):
        """Test successful text file extraction."""
        # Mock file_read_wrapped
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = 'This is test text content.\nLine 2.\nLine 3.'

            result = await text_extractor.extract(temp_text_file, 'test.txt')

            # Verify file_read_wrapped was called with correct path
            mock_read.assert_called_once_with(temp_text_file)

            # Verify result structure
            assert isinstance(result, dict)
            assert 'text' in result
            assert 'extractor' in result
            assert 'status' in result

            # Verify result values
            assert result['text'] == 'This is test text content.\nLine 2.\nLine 3.'
            assert result['extractor'] == 'strands_text'
            assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_extract_python_file_success(self, text_extractor, temp_python_file):
        """Test successful Python file extraction."""
        # Mock file_read_wrapped
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = "def hello():\n    print('Hello, world!')\n"

            result = await text_extractor.extract(temp_python_file, 'script.py')

            # Verify result
            assert result['text'] == "def hello():\n    print('Hello, world!')\n"
            assert result['status'] == 'success'
            assert result['extractor'] == 'strands_text'

    @pytest.mark.asyncio
    async def test_extract_json_file_success(self, text_extractor, temp_json_file):
        """Test successful JSON file extraction."""
        # Mock file_read_wrapped
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = '{"name": "test", "value": 123}'

            result = await text_extractor.extract(temp_json_file, 'config.json')

            # Verify result
            assert result['text'] == '{"name": "test", "value": 123}'
            assert result['status'] == 'success'
            assert result['extractor'] == 'strands_text'

    @pytest.mark.asyncio
    async def test_extract_failure(self, text_extractor, temp_text_file):
        """Test text extraction failure handling."""
        # Mock file_read_wrapped to raise exception
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.side_effect = Exception("File read error")

            result = await text_extractor.extract(temp_text_file, 'broken.txt')

            # Verify result structure for error case
            assert isinstance(result, dict)
            assert 'text' in result
            assert 'extractor' in result
            assert 'status' in result

            # Verify error handling
            assert '[Text extraction failed:' in result['text']
            assert 'File read error' in result['text']
            assert result['extractor'] == 'strands_text'
            assert result['status'] == 'error'

    @pytest.mark.asyncio
    async def test_extract_empty_file(self, text_extractor, temp_text_file):
        """Test extraction from empty file."""
        # Mock file_read_wrapped returning empty string
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = ''

            result = await text_extractor.extract(temp_text_file, 'empty.txt')

            # Verify empty text is handled correctly
            assert result['text'] == ''
            assert result['status'] == 'success'
            assert result['extractor'] == 'strands_text'

    @pytest.mark.asyncio
    async def test_extract_with_unicode(self, text_extractor, temp_text_file):
        """Test extraction with Unicode characters."""
        # Mock file_read_wrapped returning Unicode text
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = 'Hello 世界\nРусский текст\n🚀 Emoji'

            result = await text_extractor.extract(temp_text_file, 'unicode.txt')

            # Verify Unicode is preserved
            assert result['text'] == 'Hello 世界\nРусский текст\n🚀 Emoji'
            assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_extract_large_file(self, text_extractor, temp_text_file):
        """Test extraction of large text file."""
        # Mock file_read_wrapped returning large text
        large_text = "Line of code\n" * 50000  # 50000 lines
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.return_value = large_text

            result = await text_extractor.extract(temp_text_file, 'large.txt')

            # Verify large text is handled
            assert len(result['text']) == len(large_text)
            assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_extract_markdown_with_formatting(self, text_extractor, temp_text_file):
        """Test extraction of Markdown with formatting."""
        # Mock file_read_wrapped with Markdown content
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            markdown_content = """# Header 1
## Header 2

**Bold text** and *italic text*

- List item 1
- List item 2

```python
def hello():
    print("world")
```
"""
            mock_read.return_value = markdown_content

            result = await text_extractor.extract(temp_text_file, 'README.md')

            # Verify Markdown formatting is preserved
            assert '# Header 1' in result['text']
            assert '**Bold text**' in result['text']
            assert '```python' in result['text']
            assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_extract_yaml_config(self, text_extractor, temp_text_file):
        """Test extraction of YAML configuration."""
        # Mock file_read_wrapped with YAML content
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            yaml_content = """version: "3.8"
services:
  app:
    image: python:3.11
    ports:
      - "8000:8000"
"""
            mock_read.return_value = yaml_content

            result = await text_extractor.extract(temp_text_file, 'docker-compose.yml')

            # Verify YAML content is preserved
            assert 'version: "3.8"' in result['text']
            assert 'services:' in result['text']
            assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_extract_permission_error(self, text_extractor, temp_text_file):
        """Test handling of permission errors."""
        # Mock file_read_wrapped to raise PermissionError
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.side_effect = PermissionError("Access denied")

            result = await text_extractor.extract(temp_text_file, 'protected.txt')

            # Verify error handling
            assert result['status'] == 'error'
            assert '[Text extraction failed:' in result['text']
            assert 'Access denied' in result['text']

    @pytest.mark.asyncio
    async def test_extract_file_not_found(self, text_extractor):
        """Test handling of file not found errors."""
        # Mock file_read_wrapped to raise FileNotFoundError
        with patch('app.tools.strands_tools_wrapped.file_read_wrapped') as mock_read:
            mock_read.side_effect = FileNotFoundError("File not found")

            result = await text_extractor.extract('/nonexistent/file.txt', 'missing.txt')

            # Verify error handling
            assert result['status'] == 'error'
            assert '[Text extraction failed:' in result['text']
            assert 'File not found' in result['text']

    def test_initialization_no_dependencies(self):
        """Test TextExtractor initialization requires no dependencies."""
        # TextExtractor should initialize without any parameters
        extractor = TextExtractor()

        # Verify instance is created successfully
        assert extractor is not None

    def test_liskov_substitution_principle(self, text_extractor):
        """Test that TextExtractor can be used as IContentExtractor."""
        from app.services.extractors.interface import IContentExtractor

        # Verify TextExtractor implements IContentExtractor
        assert isinstance(text_extractor, IContentExtractor)

        # Verify all required methods exist
        assert hasattr(text_extractor, 'supported_extensions')
        assert hasattr(text_extractor, 'supported_mime_types')
        assert hasattr(text_extractor, 'extract')

        # Verify methods are callable
        assert callable(text_extractor.supported_extensions)
        assert callable(text_extractor.supported_mime_types)
        assert callable(text_extractor.extract)

    def test_wide_file_type_support(self, text_extractor):
        """Test that TextExtractor supports wide variety of text file types."""
        extensions = text_extractor.supported_extensions()

        # Should support many file types (Single Responsibility: all text-based files)
        assert len(extensions) >= 24  # At least 24 different file types

        # Should handle multiple programming languages
        programming_extensions = {'.py', '.js', '.rs', '.go', '.c', '.cpp'}
        assert programming_extensions.issubset(extensions)

        # Should handle multiple config formats
        config_extensions = {'.json', '.yaml', '.toml'}
        assert config_extensions.issubset(extensions)
