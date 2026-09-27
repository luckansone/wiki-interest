"""Data layer: retry, cache and request shapes.

HTTP retry honors Retry-After (Wikidata's anonymous limit answers 429 + Retry-After ~15 s), the cache
survives corrupt entries, and requests do not depend on --months or the language list.
"""

import datetime as dt

import pytest

from wiki_interest.config import MAX_ATTEMPTS
from wiki_interest.data import http, wikimedia
from wiki_interest.errors import ApiError, TopicNotFoundError


class _Resp:
    def __init__(self, code, body=None, headers=None):
        self.status_code, self._body, self.headers = code, body, headers or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        pass


@pytest.fixture
def net(monkeypatch, tmp_path):
    monkeypatch.setenv("WI_CACHE", str(tmp_path))
    for var in ("WI_OFFLINE", "WI_FAKE_API"):
        monkeypatch.delenv(var, raising=False)
    sleeps = []
    monkeypatch.setattr(http.time, "sleep", sleeps.append)

    def use(responses):
        it = iter(responses)
        monkeypatch.setattr(http.requests, "get", lambda *a, **k: next(it))

    return use, sleeps


def test_429_waits_retry_after_then_succeeds(net):
    use, sleeps = net
    use([_Resp(429, headers={"Retry-After": "14"}), _Resp(200, {"ok": 1})])
    assert http.get_json("https://x/api", {"a": 1}) == {"ok": 1}
    assert sleeps == [15]


def test_gives_up_without_trailing_sleep(net):
    use, sleeps = net
    use([_Resp(503)] * MAX_ATTEMPTS)
    with pytest.raises(ApiError, match="HTTP 503"):
        http.get_json("https://x/api")
    assert len(sleeps) == MAX_ATTEMPTS - 1


def test_corrupt_cache_entry_is_a_miss(net, tmp_path):
    use, _ = net
    http.cache_path("https://x/api", None, tmp_path).write_text('{"fetched_at": 1, "bo')  # half-written
    use([_Resp(200, {"ok": 2})])
    assert http.get_json("https://x/api") == {"ok": 2}


def test_requests_do_not_depend_on_months_or_langs(monkeypatch):
    """Follow-ups ('over 3 years', 'add Slovak') must hit the same cache entries."""
    seen = []
    monkeypatch.setattr(http, "get_json", lambda url, params=None, ttl_s=None: seen.append((url, params)) or {})
    today = dt.date(2026, 9, 27)
    wikimedia.article_views("pl", "Astronomia", wikimedia.month_window(24, today))
    wikimedia.article_views("pl", "Astronomia", wikimedia.month_window(36, today))
    wikimedia.project_views("pl", wikimedia.month_window(24, today))
    wikimedia.project_views("pl", wikimedia.month_window(60, today))
    with pytest.raises(TopicNotFoundError):  # empty body -> not found, but the request is what we check
        wikimedia.resolve_topic("Astronomy", ["pl"])
    with pytest.raises(TopicNotFoundError):
        wikimedia.resolve_topic("Astronomy", ["pl", "sk"])
    assert seen[0] == seen[1] and seen[2] == seen[3] and seen[4] == seen[5]


def test_cache_key_format_is_stable(tmp_path):
    """Changing the key format silently throws away every cached response of every user."""
    p = http.cache_path("https://wikimedia.org/x", {"b": 2, "a": 1}, tmp_path)
    assert p.name == "b9cae7db97926f2ec55185fa23e0736859081057.json"


def test_offline_mode_without_cache_fails_with_a_fix(net, monkeypatch):
    monkeypatch.setenv("WI_OFFLINE", "1")
    with pytest.raises(ApiError) as e:
        http.get_json("https://x/never-cached")
    assert "WI_OFFLINE" in e.value.fix
