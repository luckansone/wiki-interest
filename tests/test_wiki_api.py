"""HTTP layer: retry honors Retry-After (Wikidata's anonymous limit answers 429 + Retry-After ~15 s)."""

import pytest

import wiki_api


class _Resp:
    def __init__(self, code, body=None, headers=None):
        self.status_code, self._body, self.headers = code, body, headers or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        pass


@pytest.fixture
def net(monkeypatch, tmp_path):
    monkeypatch.setattr(wiki_api, "CACHE_DIR", tmp_path)
    monkeypatch.delenv("WI_OFFLINE", raising=False)
    sleeps = []
    monkeypatch.setattr(wiki_api.time, "sleep", sleeps.append)

    def use(responses):
        it = iter(responses)
        monkeypatch.setattr(wiki_api.requests, "get", lambda *a, **k: next(it))

    return use, sleeps


def test_429_waits_retry_after_then_succeeds(net):
    use, sleeps = net
    use([_Resp(429, headers={"Retry-After": "14"}), _Resp(200, {"ok": 1})])
    assert wiki_api.http_get_json("https://x/api", {"a": 1}) == {"ok": 1}
    assert sleeps == [15]


def test_gives_up_without_trailing_sleep(net):
    use, sleeps = net
    use([_Resp(503)] * wiki_api.MAX_ATTEMPTS)
    with pytest.raises(wiki_api.ApiError, match="HTTP 503"):
        wiki_api.http_get_json("https://x/api")
    assert len(sleeps) == wiki_api.MAX_ATTEMPTS - 1


def test_corrupt_cache_entry_is_a_miss(net):
    use, _ = net
    wiki_api._cache_path("https://x/api", None).write_text('{"fetched_at": 1, "bo')  # half-written
    use([_Resp(200, {"ok": 2})])
    assert wiki_api.http_get_json("https://x/api") == {"ok": 2}


def test_requests_do_not_depend_on_months_or_langs(monkeypatch):
    """Follow-ups ('over 3 years', 'add Slovak') must hit the same cache entries."""
    import datetime as dt

    seen = []
    monkeypatch.setattr(
        wiki_api, "http_get_json", lambda url, params=None, ttl_s=None: seen.append((url, params)) or {}
    )
    today = dt.date(2026, 9, 27)
    wiki_api.article_views("pl", "Astronomia", wiki_api.month_window(24, today))
    wiki_api.article_views("pl", "Astronomia", wiki_api.month_window(36, today))
    wiki_api.project_views("pl", wiki_api.month_window(24, today))
    wiki_api.project_views("pl", wiki_api.month_window(60, today))
    with pytest.raises(wiki_api.ApiError):  # empty body -> not found, but the request is what we check
        wiki_api.resolve_topic("Astronomy", ["pl"])
    with pytest.raises(wiki_api.ApiError):
        wiki_api.resolve_topic("Astronomy", ["pl", "sk"])
    assert seen[0] == seen[1] and seen[2] == seen[3] and seen[4] == seen[5]
