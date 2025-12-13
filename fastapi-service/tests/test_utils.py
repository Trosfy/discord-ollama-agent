"""Unit tests for utility functions."""
import pytest

from app.utils.message_splitter import split_message
from app.utils.validators import validate_model, validate_temperature


def test_split_message_no_split_needed():
    """Test that short messages are not split."""
    content = "Hello, world!"
    chunks = split_message(content)

    assert len(chunks) == 1
    assert chunks[0] == content


def test_split_message_splits_long_message():
    """Test that long messages are split."""
    # Create a message longer than 2000 characters
    content = "word " * 500  # 2500 characters
    chunks = split_message(content, max_length=2000)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 2000


def test_split_message_preserves_words():
    """Test that message splitting preserves word boundaries."""
    content = "Hello world this is a test message"
    chunks = split_message(content, max_length=20)

    # Each chunk should contain complete words
    for chunk in chunks:
        # Remove part indicators if present
        if chunk.startswith("[Part"):
            chunk = chunk.split("\n", 1)[1] if "\n" in chunk else chunk

        assert not chunk.startswith(" ")
        assert not chunk.endswith(" word")  # No partial words


def test_split_message_adds_part_indicators():
    """Test that part indicators are added to split messages."""
    content = "word " * 500
    chunks = split_message(content, max_length=2000)

    if len(chunks) > 1:
        for i, chunk in enumerate(chunks):
            assert chunk.startswith(f"[Part {i+1}/{len(chunks)}]")


def test_split_message_preserves_newlines():
    """Test that newlines are preserved in split messages."""
    content = "Line 1\nLine 2\nLine 3\n" * 100
    chunks = split_message(content, max_length=500)

    for chunk in chunks:
        # Remove part indicator
        if chunk.startswith("[Part"):
            chunk = chunk.split("\n", 1)[1]

        # Should contain newlines, not spaces
        assert "\n" in chunk
        lines = chunk.split("\n")
        # Each line should be from the original content
        for line in lines:
            if line:  # Skip empty lines
                assert line in ["Line 1", "Line 2", "Line 3"]


def test_split_message_preserves_code_blocks():
    """Test that code block formatting is preserved."""
    content = """Here's a function:

```python
def foo():
    return 42
```

And here's another:

```python
def bar():
    return 99
```"""
    chunks = split_message(content, max_length=2000)

    # Should preserve code block structure
    full_result = '\n'.join(
        chunk.split('\n', 1)[1] if chunk.startswith('[Part') else chunk
        for chunk in chunks
    )
    assert '```python' in full_result
    assert '    return 42' in full_result  # Indentation preserved
    assert 'def foo():' in full_result
    assert 'def bar():' in full_result


def test_split_message_preserves_lists():
    """Test that list formatting is preserved."""
    content = """Analysis:

1. First point
2. Second point
3. Third point

- Bullet A
- Bullet B
- Bullet C"""
    chunks = split_message(content, max_length=500)

    full_result = '\n'.join(
        chunk.split('\n', 1)[1] if chunk.startswith('[Part') else chunk
        for chunk in chunks
    )
    assert '1. First point' in full_result
    assert '2. Second point' in full_result
    assert '3. Third point' in full_result
    assert '- Bullet A' in full_result
    assert '- Bullet B' in full_result
    assert '- Bullet C' in full_result


def test_split_very_long_single_line():
    """Test fallback for single line that exceeds max length."""
    # Single line with no newlines, very long
    content = "word " * 500
    chunks = split_message(content, max_length=2000)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 2000


def test_validate_model_default():
    """Test model validation with None returns default."""
    model = validate_model(None)
    assert model == "gpt-oss:20b"


def test_validate_model_valid():
    """Test model validation with valid model."""
    model = validate_model("gpt-oss:20b")
    assert model == "gpt-oss:20b"


def test_validate_model_invalid():
    """Test model validation with invalid model raises error."""
    with pytest.raises(ValueError, match="not available"):
        validate_model("invalid-model")


def test_validate_temperature_default():
    """Test temperature validation with None returns default."""
    temp = validate_temperature(None)
    assert temp == 0.7


def test_validate_temperature_valid():
    """Test temperature validation with valid value."""
    temp = validate_temperature(1.0)
    assert temp == 1.0


def test_validate_temperature_too_low():
    """Test temperature validation rejects values below 0."""
    with pytest.raises(ValueError, match="between 0.0 and 2.0"):
        validate_temperature(-0.1)


def test_validate_temperature_too_high():
    """Test temperature validation rejects values above 2."""
    with pytest.raises(ValueError, match="between 0.0 and 2.0"):
        validate_temperature(2.1)


def test_validate_temperature_boundary_values():
    """Test temperature validation accepts boundary values."""
    assert validate_temperature(0.0) == 0.0
    assert validate_temperature(2.0) == 2.0
