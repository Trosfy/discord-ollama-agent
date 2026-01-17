"""Reusable condition functions for graph edges.

These conditions are evaluated at runtime to determine which edge
to follow in a graph. They receive the current GraphState and return
a boolean indicating whether the edge should be taken.

Conditions are registered by name and can be referenced in YAML
graph definitions.

Example YAML usage:
    edges:
      code_reviewer:
        - to: debugger
          condition: has_issues
        - to: test_generator
          condition: review_passed
"""
from typing import Callable, Dict

from app.core.interfaces.graph import GraphState


# =============================================================================
# Code Review Conditions
# =============================================================================

def has_issues(state: GraphState) -> bool:
    """Check if code review found issues.

    Args:
        state: Current graph state.

    Returns:
        True if review_issues list is non-empty.
    """
    issues = state.get("review_issues", [])
    return len(issues) > 0


def review_passed(state: GraphState) -> bool:
    """Check if code review passed (no issues).

    Args:
        state: Current graph state.

    Returns:
        True if no review issues found.
    """
    return not has_issues(state)


# =============================================================================
# Test Conditions
# =============================================================================

def tests_failed(state: GraphState) -> bool:
    """Check if tests failed.

    Args:
        state: Current graph state.

    Returns:
        True if test_results.passed is False.
    """
    test_results = state.get("test_results", {})
    return test_results.get("passed") is False


def tests_passed(state: GraphState) -> bool:
    """Check if tests passed.

    Args:
        state: Current graph state.

    Returns:
        True if test_results.passed is True.
    """
    test_results = state.get("test_results", {})
    return test_results.get("passed") is True


# =============================================================================
# Research Conditions
# =============================================================================

def has_sufficient_knowledge(state: GraphState) -> bool:
    """Check if explorer found sufficient existing knowledge.

    Args:
        state: Current graph state.

    Returns:
        True if knowledge_score >= 0.7.
    """
    score = state.get("knowledge_score", 0)
    return score >= 0.7


def needs_more_research(state: GraphState) -> bool:
    """Check if more research is needed.

    Args:
        state: Current graph state.

    Returns:
        True if knowledge is insufficient.
    """
    return not has_sufficient_knowledge(state)


def needs_more_sources(state: GraphState) -> bool:
    """Check if fact checker needs more sources.

    Args:
        state: Current graph state.

    Returns:
        True if unverified_claims list is non-empty.
    """
    unverified = state.get("unverified_claims", [])
    return len(unverified) > 0


def facts_verified(state: GraphState) -> bool:
    """Check if all facts have been verified.

    Args:
        state: Current graph state.

    Returns:
        True if no unverified claims remain.
    """
    return not needs_more_sources(state)


# =============================================================================
# Braindump Conditions
# =============================================================================

def rich_connections(state: GraphState) -> bool:
    """Check if vault connector found rich connections.

    Rich connections (3+) trigger the insight extractor for
    deeper analysis before formatting.

    Args:
        state: Current graph state.

    Returns:
        True if 3 or more vault connections found.
    """
    connections = state.get("vault_connections", [])
    return len(connections) >= 3


def sparse_connections(state: GraphState) -> bool:
    """Check if vault connector found sparse connections.

    Sparse connections skip insight extraction and go directly
    to note formatting.

    Args:
        state: Current graph state.

    Returns:
        True if fewer than 3 vault connections found.
    """
    return not rich_connections(state)


# =============================================================================
# Generic/Utility Conditions
# =============================================================================

def always_true(state: GraphState) -> bool:
    """Unconditional edge (always taken).

    Use this explicitly when you want to document that an edge
    is unconditional in the YAML.

    Args:
        state: Current graph state (unused).

    Returns:
        Always True.
    """
    return True


def has_errors(state: GraphState) -> bool:
    """Check if any node reported errors.

    Args:
        state: Current graph state.

    Returns:
        True if errors list is non-empty.
    """
    errors = state.get("errors", [])
    return len(errors) > 0


def no_errors(state: GraphState) -> bool:
    """Check if no errors have been reported.

    Args:
        state: Current graph state.

    Returns:
        True if errors list is empty.
    """
    return not has_errors(state)


def loop_limit_reached(state: GraphState) -> bool:
    """Check if loop iteration limit has been reached.

    Args:
        state: Current graph state.

    Returns:
        True if loop_count >= max_loops.
    """
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 3)
    return loop_count >= max_loops


# =============================================================================
# Test Generation Conditions
# =============================================================================

def needs_tests(state: GraphState) -> bool:
    """Check if tests should be generated.

    Returns True if:
    - User explicitly requested tests ("with tests", "test this", etc.)
    - Code appears complex (multiple functions, classes, etc.)

    Args:
        state: Current graph state.

    Returns:
        True if test generation is warranted.
    """
    user_input = state.get("input", "").lower()

    # Explicit test request keywords
    test_keywords = [
        "test", "tests", "with tests", "unit test", "test cases",
        "write tests", "add tests", "include tests"
    ]
    if any(keyword in user_input for keyword in test_keywords):
        return True

    # Check complexity from code_reviewer output
    review_content = state.get("code_reviewer", "").lower()
    complexity_signals = [
        "multiple functions", "class", "complex", "integration",
        "requires testing", "should be tested"
    ]
    if any(signal in review_content for signal in complexity_signals):
        return True

    return False


def simple_approval(state: GraphState) -> bool:
    """Check if code passed review and doesn't need tests.

    Used to skip test_generator for simple requests that don't
    explicitly ask for tests.

    Args:
        state: Current graph state.

    Returns:
        True if review passed and no tests needed.
    """
    return review_passed(state) and not needs_tests(state)


# =============================================================================
# Condition Registry
# =============================================================================

# Map condition names (as used in YAML) to functions
CONDITIONS: Dict[str, Callable[[GraphState], bool]] = {
    # Code review
    "has_issues": has_issues,
    "review_passed": review_passed,
    "needs_tests": needs_tests,
    "simple_approval": simple_approval,

    # Tests
    "tests_failed": tests_failed,
    "tests_passed": tests_passed,

    # Research
    "has_sufficient_knowledge": has_sufficient_knowledge,
    "needs_more_research": needs_more_research,
    "needs_more_sources": needs_more_sources,
    "facts_verified": facts_verified,

    # Braindump
    "rich_connections": rich_connections,
    "sparse_connections": sparse_connections,

    # Generic
    "always_true": always_true,
    "has_errors": has_errors,
    "no_errors": no_errors,
    "loop_limit_reached": loop_limit_reached,
}


def get_condition(name: str) -> Callable[[GraphState], bool]:
    """Get a condition function by name.

    Args:
        name: Condition name as used in YAML.

    Returns:
        Condition function.

    Raises:
        KeyError: If condition name is not registered.
    """
    if name not in CONDITIONS:
        raise KeyError(f"Unknown condition: '{name}'. Available: {list(CONDITIONS.keys())}")
    return CONDITIONS[name]


def register_condition(name: str, condition: Callable[[GraphState], bool]) -> None:
    """Register a custom condition function.

    Allows plugins or custom code to add new conditions without
    modifying this module (Open/Closed Principle).

    Args:
        name: Name to use in YAML definitions.
        condition: Function taking GraphState and returning bool.
    """
    CONDITIONS[name] = condition
