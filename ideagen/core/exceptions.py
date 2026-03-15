class IdeaGenError(Exception):
    """Base exception for IdeaGen."""

class SourceUnavailableError(IdeaGenError):
    """A data source is unavailable."""

class ProviderError(IdeaGenError):
    """AI provider error."""

class ProviderTimeoutError(ProviderError):
    """AI provider timed out — not retryable."""

class ConfigError(IdeaGenError):
    """Configuration error."""

class StorageError(IdeaGenError):
    """Storage backend error."""
