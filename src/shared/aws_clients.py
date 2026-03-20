"""Boto3 client factory with X-Ray tracing support.

Provides a centralized factory for creating and caching AWS service clients,
with automatic X-Ray tracing instrumentation when available.
"""

from typing import Any

import boto3

_client_cache: dict[str, Any] = {}

# Attempt to patch boto3 with X-Ray tracing
try:
    from aws_xray_sdk.core import patch_all
    patch_all()
except ImportError:
    pass


def get_client(service_name: str, **kwargs: Any) -> Any:
    """Get or create a cached boto3 client for the specified AWS service.

    Clients are cached at module level to enable reuse across Lambda
    invocations within the same execution environment.

    Args:
        service_name: AWS service name (e.g., 'ec2', 'ssm', 'cloudwatch').
        **kwargs: Additional arguments passed to boto3.client().

    Returns:
        A boto3 service client instance.
    """
    cache_key = f"{service_name}:{hash(frozenset(kwargs.items()))}"
    if cache_key not in _client_cache:
        _client_cache[cache_key] = boto3.client(service_name, **kwargs)
    return _client_cache[cache_key]


def get_resource(service_name: str, **kwargs: Any) -> Any:
    """Get or create a cached boto3 resource for the specified AWS service.

    Args:
        service_name: AWS service name (e.g., 'dynamodb').
        **kwargs: Additional arguments passed to boto3.resource().

    Returns:
        A boto3 service resource instance.
    """
    cache_key = f"resource:{service_name}:{hash(frozenset(kwargs.items()))}"
    if cache_key not in _client_cache:
        _client_cache[cache_key] = boto3.resource(service_name, **kwargs)
    return _client_cache[cache_key]


def clear_cache() -> None:
    """Clear the client cache. Useful for testing."""
    _client_cache.clear()
