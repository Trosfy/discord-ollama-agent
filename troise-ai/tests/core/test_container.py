"""Unit tests for DI Container."""
import pytest
from typing import Protocol

from app.core.container import Container, ServiceNotFoundError


# =============================================================================
# Test Interfaces/Classes
# =============================================================================

class ITestService(Protocol):
    """Test interface for container tests."""
    def get_value(self) -> str: ...


class ServiceImpl:
    """Test implementation."""
    def __init__(self, value: str = "default"):
        self.value = value

    def get_value(self) -> str:
        return self.value


class AnotherService:
    """Another test service for hierarchical tests."""
    def __init__(self, name: str):
        self.name = name


# =============================================================================
# Singleton Registration Tests
# =============================================================================

def test_register_singleton():
    """Register and resolve singleton returns same instance."""
    container = Container()
    instance = ServiceImpl("singleton-value")

    container.register(ServiceImpl, instance)
    resolved = container.resolve(ServiceImpl)

    assert resolved is instance
    assert resolved.get_value() == "singleton-value"


def test_register_singleton_same_instance_multiple_resolves():
    """Multiple resolves return the exact same instance."""
    container = Container()
    instance = ServiceImpl("test")

    container.register(ServiceImpl, instance)

    first = container.resolve(ServiceImpl)
    second = container.resolve(ServiceImpl)
    third = container.resolve(ServiceImpl)

    assert first is second is third is instance


# =============================================================================
# Factory Registration Tests
# =============================================================================

def test_register_factory():
    """Factory creates instance on first resolve."""
    container = Container()
    call_count = 0

    def factory(c: Container) -> ServiceImpl:
        nonlocal call_count
        call_count += 1
        return ServiceImpl("factory-created")

    container.register_factory(ServiceImpl, factory)

    # Factory not called yet
    assert call_count == 0

    # First resolve triggers factory
    resolved = container.resolve(ServiceImpl)
    assert call_count == 1
    assert resolved.get_value() == "factory-created"


def test_factory_caches_result():
    """Factory only called once, result cached as singleton."""
    container = Container()
    call_count = 0

    def factory(c: Container) -> ServiceImpl:
        nonlocal call_count
        call_count += 1
        return ServiceImpl(f"call-{call_count}")

    container.register_factory(ServiceImpl, factory)

    first = container.resolve(ServiceImpl)
    second = container.resolve(ServiceImpl)
    third = container.resolve(ServiceImpl)

    # Factory called only once
    assert call_count == 1

    # All resolves return same instance
    assert first is second is third
    assert first.get_value() == "call-1"


def test_factory_receives_container():
    """Factory receives container for dependency resolution."""
    container = Container()

    # Register a dependency
    dep = AnotherService("dependency")
    container.register(AnotherService, dep)

    def factory(c: Container) -> ServiceImpl:
        # Factory can resolve other services
        another = c.resolve(AnotherService)
        return ServiceImpl(another.name)

    container.register_factory(ServiceImpl, factory)

    resolved = container.resolve(ServiceImpl)
    assert resolved.get_value() == "dependency"


# =============================================================================
# Resolution Error Tests
# =============================================================================

def test_resolve_not_found():
    """ServiceNotFoundError raised for unregistered service."""
    container = Container()

    with pytest.raises(ServiceNotFoundError) as exc_info:
        container.resolve(ServiceImpl)

    assert "ServiceImpl" in str(exc_info.value)


def test_try_resolve_returns_none():
    """try_resolve returns None instead of raising."""
    container = Container()

    result = container.try_resolve(ServiceImpl)

    assert result is None


def test_try_resolve_returns_instance_when_found():
    """try_resolve returns instance when service is registered."""
    container = Container()
    instance = ServiceImpl("found")
    container.register(ServiceImpl, instance)

    result = container.try_resolve(ServiceImpl)

    assert result is instance


# =============================================================================
# Hierarchical Container Tests
# =============================================================================

def test_hierarchical_resolution():
    """Child container resolves from parent when not found locally."""
    parent = Container()
    parent.register(ServiceImpl, ServiceImpl("parent-value"))

    child = parent.create_child()

    # Child can resolve from parent
    resolved = child.resolve(ServiceImpl)
    assert resolved.get_value() == "parent-value"


def test_child_overrides_parent():
    """Child registration shadows parent registration."""
    parent = Container()
    parent.register(ServiceImpl, ServiceImpl("parent-value"))

    child = parent.create_child()
    child.register(ServiceImpl, ServiceImpl("child-value"))

    # Parent unchanged
    assert parent.resolve(ServiceImpl).get_value() == "parent-value"

    # Child returns its own registration
    assert child.resolve(ServiceImpl).get_value() == "child-value"


def test_hierarchical_is_registered():
    """is_registered checks parent container."""
    parent = Container()
    parent.register(ServiceImpl, ServiceImpl("test"))

    child = parent.create_child()

    assert child.is_registered(ServiceImpl) is True
    assert child.is_registered(AnotherService) is False


# =============================================================================
# Unregister Tests
# =============================================================================

def test_unregister_singleton():
    """Unregister removes singleton registration."""
    container = Container()
    container.register(ServiceImpl, ServiceImpl("test"))

    assert container.is_registered(ServiceImpl) is True

    result = container.unregister(ServiceImpl)

    assert result is True
    assert container.is_registered(ServiceImpl) is False


def test_unregister_factory():
    """Unregister removes factory registration."""
    container = Container()
    container.register_factory(ServiceImpl, lambda c: ServiceImpl("test"))

    assert container.is_registered(ServiceImpl) is True

    result = container.unregister(ServiceImpl)

    assert result is True
    assert container.is_registered(ServiceImpl) is False


def test_unregister_not_found():
    """Unregister returns False when service not registered."""
    container = Container()

    result = container.unregister(ServiceImpl)

    assert result is False


# =============================================================================
# Debug/Introspection Tests
# =============================================================================

def test_list_registrations():
    """list_registrations returns correct debug info."""
    container = Container()

    # Register singleton
    container.register(ServiceImpl, ServiceImpl("test"))

    # Register factory (not yet resolved)
    container.register_factory(AnotherService, lambda c: AnotherService("test"))

    registrations = container.list_registrations()

    assert registrations["ServiceImpl"] == "singleton"
    assert registrations["AnotherService"] == "factory (pending)"


def test_list_registrations_after_factory_resolve():
    """Factory becomes singleton after first resolve."""
    container = Container()
    container.register_factory(ServiceImpl, lambda c: ServiceImpl("test"))

    # Before resolve
    before = container.list_registrations()
    assert before["ServiceImpl"] == "factory (pending)"

    # Trigger factory
    container.resolve(ServiceImpl)

    # After resolve - now shows as singleton
    after = container.list_registrations()
    assert after["ServiceImpl"] == "singleton"
