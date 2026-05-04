class AIProviderError(Exception):
    fallback_reason = "provider_error"


class MissingProviderConfigError(AIProviderError):
    fallback_reason = "missing_provider_config"


class ProviderRateLimitError(AIProviderError):
    fallback_reason = "rate_limited"


class ProviderQuotaExceededError(AIProviderError):
    fallback_reason = "quota_exceeded"


class ProviderInvalidResponseError(AIProviderError):
    fallback_reason = "invalid_response"


class ProviderInvalidJSONError(ProviderInvalidResponseError):
    fallback_reason = "invalid_json"


class ProviderHTTPError(AIProviderError):
    fallback_reason = "provider_http_error"


class ProviderUnavailableError(AIProviderError):
    fallback_reason = "provider_unavailable"
