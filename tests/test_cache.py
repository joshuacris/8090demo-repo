"""Integration tests for dashboard caching using fakeredis."""
import pytest
import fakeredis
from unittest.mock import patch
from src.cache import get_cached, set_cached, invalidate_team, _cache_key


@pytest.fixture
def fake_redis():
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)
    with patch("src.cache._client", client):
        yield client


def test_cache_miss_returns_none(fake_redis):
    assert get_cached(1, "status_breakdown") is None


def test_cache_roundtrip(fake_redis):
    data = {"todo": 5, "done": 12}
    set_cached(1, "status_breakdown", data)
    assert get_cached(1, "status_breakdown") == data


def test_invalidation_clears_specific_sections(fake_redis):
    set_cached(1, "status_breakdown", {"todo": 5})
    set_cached(1, "velocity", [{"sprint": "S1", "completed": 20}])
    set_cached(1, "workload", [{"member": "alice", "tasks": 3}])

    invalidate_team(1, ["status_breakdown", "workload"])

    assert get_cached(1, "status_breakdown") is None  # cleared
    assert get_cached(1, "velocity") is not None       # untouched
    assert get_cached(1, "workload") is None           # cleared


def test_invalidation_clears_all_sections(fake_redis):
    set_cached(1, "status_breakdown", {"todo": 5})
    set_cached(1, "velocity", [{"sprint": "S1"}])

    invalidate_team(1)  # no sections specified = all

    assert get_cached(1, "status_breakdown") is None
    assert get_cached(1, "velocity") is None


def test_redis_failure_returns_none_not_crash():
    """When Redis is down, cache ops should return None / no-op, not raise."""
    with patch("src.cache._client") as mock_client:
        mock_client.get.side_effect = Exception("Connection refused")
        assert get_cached(1, "status_breakdown") is None

        mock_client.setex.side_effect = Exception("Connection refused")
        set_cached(1, "status_breakdown", {"test": 1})  # should not raise
