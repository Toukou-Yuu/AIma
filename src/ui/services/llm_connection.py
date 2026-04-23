"""LLM connection probing service for UI summaries."""

from __future__ import annotations

import threading

ConnectionCacheKey = tuple[str, str, str, str]
ConnectionProbeStatus = tuple[str, str, str]

_DEFAULT_TIMEOUT_SEC = 1.5
_PROBE_CACHE: dict[ConnectionCacheKey, ConnectionProbeStatus] = {}
_PROBE_IN_FLIGHT: set[ConnectionCacheKey] = set()
_PROBE_LOCK = threading.Lock()


def probe_connection_status(
    *,
    provider: str,
    base_url: str,
    api_key: str,
    configured: bool,
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
) -> ConnectionProbeStatus:
    """Probe whether an LLM endpoint is reachable."""
    if not configured:
        return ("未连接", "yellow", "缺少 API Key")

    try:
        if provider == "anthropic":
            result = _probe_anthropic_connection(
                base_url=base_url,
                api_key=api_key,
                timeout_sec=timeout_sec,
            )
        else:
            result = _probe_openai_connection(
                base_url=base_url,
                api_key=api_key,
                timeout_sec=timeout_sec,
            )
    except ImportError:
        result = ("未检查", "yellow", "缺少 httpx")
    except Exception as exc:
        try:
            import httpx
        except ImportError:
            result = ("未检查", "yellow", exc.__class__.__name__)
        else:
            if isinstance(exc, httpx.TimeoutException):
                result = ("未连接", "yellow", "探测超时")
            elif isinstance(exc, httpx.HTTPError):
                result = ("未连接", "yellow", exc.__class__.__name__)
            else:
                result = ("未连接", "yellow", exc.__class__.__name__)
    return result


def get_cached_probe_status(cache_key: ConnectionCacheKey) -> ConnectionProbeStatus | None:
    """Return a cached probe result, if present."""
    with _PROBE_LOCK:
        return _PROBE_CACHE.get(cache_key)


def schedule_probe_refresh(
    *,
    cache_key: ConnectionCacheKey,
    provider: str,
    base_url: str,
    api_key: str,
    configured: bool,
) -> None:
    """Refresh a probe result in the background without blocking rendering."""
    with _PROBE_LOCK:
        if cache_key in _PROBE_IN_FLIGHT:
            return
        _PROBE_IN_FLIGHT.add(cache_key)

    def worker() -> None:
        try:
            result = probe_connection_status(
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                configured=configured,
            )
            _store_probe_status(cache_key, result)
        except Exception:
            _store_probe_status(cache_key, ("未连接", "yellow", "探测失败"))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


def _probe_openai_connection(
    *,
    base_url: str,
    api_key: str,
    timeout_sec: float,
) -> ConnectionProbeStatus:
    """Probe an OpenAI-compatible models endpoint."""
    import httpx

    url = base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=timeout_sec) as client:
        response = client.get(url, headers=headers)
    if response.status_code == 200:
        return ("已连接", "green", "接口可达")
    if response.status_code in (401, 403):
        return ("鉴权失败", "red", f"HTTP {response.status_code}")
    return ("连接异常", "yellow", f"HTTP {response.status_code}")


def _probe_anthropic_connection(
    *,
    base_url: str,
    api_key: str,
    timeout_sec: float,
) -> ConnectionProbeStatus:
    """Probe an Anthropic models endpoint."""
    import httpx

    url = base_url.rstrip("/") + "/v1/models"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    with httpx.Client(timeout=timeout_sec) as client:
        response = client.get(url, headers=headers)
    if response.status_code == 200:
        return ("已连接", "green", "接口可达")
    if response.status_code in (401, 403):
        return ("鉴权失败", "red", f"HTTP {response.status_code}")
    return ("连接异常", "yellow", f"HTTP {response.status_code}")


def _store_probe_status(
    cache_key: ConnectionCacheKey,
    result: ConnectionProbeStatus,
) -> None:
    """Store the latest probe result and mark refresh as complete."""
    with _PROBE_LOCK:
        _PROBE_CACHE[cache_key] = result
        _PROBE_IN_FLIGHT.discard(cache_key)
