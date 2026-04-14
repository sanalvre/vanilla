"""
Unit tests for watcher_bridge.py — debounce queue and file event handling.

These tests use a very short debounce (0.1s) for speed. The real debounce is 300s.
"""

import asyncio
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sidecar"))

from db.database import init_db
from db import database as db_module
from services.watcher_bridge import WatcherBridge, FileEvent


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Watcher bridge checks sync_writes table, so we need a DB."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    yield
    if db_module._connection:
        db_module._connection.close()
    db_module._connection = None


@pytest.fixture
def dispatched_events():
    """Collects events that pass through the debounce."""
    return []


@pytest.fixture
def bridge(dispatched_events, tmp_path):
    """Create a watcher bridge with 0.1s debounce for fast testing."""
    async def on_ready(event):
        dispatched_events.append(event)

    return WatcherBridge(
        debounce_seconds=0.1,  # 100ms for testing (real is 300s)
        on_ready=on_ready,
        vault_root=str(tmp_path),
    )


class TestWatcherBridge:
    @pytest.mark.asyncio
    async def test_event_dispatched_after_debounce(self, bridge, dispatched_events, tmp_path):
        """File event should be dispatched after debounce period."""
        # Create a test file so hash can be computed
        test_file = tmp_path / "clean-vault" / "raw" / "test.md"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("hello world")

        await bridge.start()
        event = FileEvent("clean-vault/raw/test.md", "create", int(time.time()))
        await bridge.push_event(event)

        # Wait for debounce (0.1s) + processing time
        await asyncio.sleep(0.4)
        await bridge.stop()

        assert len(dispatched_events) == 1
        assert dispatched_events[0].path == "clean-vault/raw/test.md"

    @pytest.mark.asyncio
    async def test_debounce_resets_on_new_event(self, bridge, dispatched_events, tmp_path):
        """New event for same path should reset the debounce timer."""
        test_file = tmp_path / "test.md"
        test_file.write_text("v1")

        await bridge.start()

        # First event
        await bridge.push_event(FileEvent("test.md", "modify", int(time.time())))
        await asyncio.sleep(0.05)  # Before debounce expires

        # Second event for same path — should reset timer
        test_file.write_text("v2")
        await bridge.push_event(FileEvent("test.md", "modify", int(time.time())))

        # Wait for new debounce
        await asyncio.sleep(0.3)
        await bridge.stop()

        # Should only dispatch once (the reset one)
        assert len(dispatched_events) == 1

    @pytest.mark.asyncio
    async def test_different_paths_debounce_independently(self, bridge, dispatched_events, tmp_path):
        """Events for different paths should have independent debounce timers."""
        (tmp_path / "a.md").write_text("aaa")
        (tmp_path / "b.md").write_text("bbb")

        await bridge.start()
        await bridge.push_event(FileEvent("a.md", "create", int(time.time())))
        await bridge.push_event(FileEvent("b.md", "create", int(time.time())))

        await asyncio.sleep(0.4)
        await bridge.stop()

        assert len(dispatched_events) == 2
        paths = {e.path for e in dispatched_events}
        assert paths == {"a.md", "b.md"}

    @pytest.mark.asyncio
    async def test_force_dispatch_all(self, bridge, dispatched_events, tmp_path):
        """force_dispatch_all should bypass debounce."""
        (tmp_path / "a.md").write_text("aaa")
        (tmp_path / "b.md").write_text("bbb")

        await bridge.start()
        await bridge.push_event(FileEvent("a.md", "create", int(time.time())))
        await bridge.push_event(FileEvent("b.md", "create", int(time.time())))

        # Give queue time to process events into pending
        await asyncio.sleep(0.05)

        count = await bridge.force_dispatch_all()
        await bridge.stop()

        assert count == 2
        assert len(dispatched_events) == 2

    @pytest.mark.asyncio
    async def test_get_pending_count(self, bridge, tmp_path):
        """Pending count should reflect queued events."""
        (tmp_path / "test.md").write_text("content")

        await bridge.start()
        await bridge.push_event(FileEvent("test.md", "create", int(time.time())))

        await asyncio.sleep(0.05)  # Let queue process
        assert bridge.get_pending_count() >= 1

        await bridge.stop()

    @pytest.mark.asyncio
    async def test_delete_event_dispatches_regardless(self, bridge, dispatched_events, tmp_path):
        """Delete events should dispatch even without hash match."""
        await bridge.start()
        event = FileEvent("deleted.md", "delete", int(time.time()))
        await bridge.push_event(event)

        await asyncio.sleep(0.3)
        await bridge.stop()

        assert len(dispatched_events) == 1
        assert dispatched_events[0].event_type == "delete"

    @pytest.mark.asyncio
    async def test_get_pending_paths(self, bridge, tmp_path):
        """Should return list of paths waiting in debounce queue."""
        (tmp_path / "file.md").write_text("x")

        await bridge.start()
        await bridge.push_event(FileEvent("file.md", "create", int(time.time())))
        await asyncio.sleep(0.05)

        paths = bridge.get_pending_paths()
        assert "file.md" in paths

        await bridge.stop()
