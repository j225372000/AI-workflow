from src.providers.gemini_provider import GeminiProvider


_PROVIDER_CACHE = {}


def get_provider(provider_name: str = "gemini"):
    if provider_name in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[provider_name]

    if provider_name == "gemini":
        provider = GeminiProvider()
    else:
        raise ValueError(f"未知 Provider：{provider_name}")

    _PROVIDER_CACHE[provider_name] = provider
    return provider
