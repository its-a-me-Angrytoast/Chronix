import os
from chronix_bot.utils import music_queue


def _clear_file():
    f = music_queue.QUEUES_FILE
    if f.exists():
        f.unlink()


def test_enqueue_and_dequeue():
    _clear_file()
    gid = 999
    music_queue.enqueue(gid, {"title": "Song A", "url": "http://a", "requested_by": 1})
    music_queue.enqueue(gid, {"title": "Song B", "url": "http://b", "requested_by": 2})
    q = music_queue.list_queue(gid)
    assert len(q) == 2
    first = music_queue.dequeue(gid)
    assert first["title"] == "Song A"
    second = music_queue.dequeue(gid)
    assert second["title"] == "Song B"
    assert music_queue.dequeue(gid) is None


def test_panel_and_volume_metadata():
    _clear_file()
    gid = 42
    music_queue.set_panel_message(gid, 123, 456)
    meta = music_queue.get_panel_message(gid)
    assert meta and meta.get("panel_channel") == 123 and meta.get("panel_message") == 456
    # volume default
    assert music_queue.get_volume(gid) == 100
    music_queue.set_volume(gid, 80)
    assert music_queue.get_volume(gid) == 80
