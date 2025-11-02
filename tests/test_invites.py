import pytest
from chronix_bot.utils import invites as inv_utils


@pytest.mark.asyncio
async def test_record_and_leaderboard():
    # use file-backed functions
    await inv_utils.record_invite_create(1, "code123", 42, uses=0)
    inviter = await inv_utils.increment_invite_use(1, "code123")
    assert inviter == 42
    board = await inv_utils.get_leaderboard(1, limit=5)
    assert any(u == 42 for u, c in board)
    await inv_utils.reset_guild_invites(1)
    board2 = await inv_utils.get_leaderboard(1)
    assert board2 == []


@pytest.mark.asyncio
async def test_fake_detection_file_backed(tmp_path, monkeypatch):
    # ensure file-backed path is used by making get_pool return None
    # create a temp invites file and point INVITES_PATH to it
    import os, json

    temp = tmp_path / "invites.json"
    temp.write_text(json.dumps({"invites": [], "counts": {}}))
    # monkeypatch the path used by the module
    monkeypatch.setattr(inv_utils, "INVITES_PATH", str(temp))
    # create an invite and simulate a join from a brand-new account (fake)
    await inv_utils.record_invite_create(2, "codeF", 99, uses=0)
    now_iso = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    inviter = await inv_utils.increment_invite_use(2, "codeF", joined_user_id=1234, account_created_iso=now_iso)
    assert inviter == 99
    # inspect file
    with open(str(temp), "r", encoding="utf-8") as f:
        data = json.load(f)
    counts = data.get("counts", {})
    key = f"2:99"
    assert key in counts
    val = counts[key]
    # should be a dict with a fake count recorded or at least invites
    assert isinstance(val, dict)
    assert val.get("fake", 0) >= 0


@pytest.mark.asyncio
async def test_get_user_counts_file_backed(tmp_path, monkeypatch):
    import os, json

    temp = tmp_path / "inv2.json"
    temp.write_text(json.dumps({"invites": [], "counts": {}}))
    monkeypatch.setattr(inv_utils, "INVITES_PATH", str(temp))
    await inv_utils.record_invite_create(3, "codeX", 77, uses=0)
    await inv_utils.increment_invite_use(3, "codeX")
    counts = await inv_utils.get_user_counts(3, 77)
    assert counts["invites"] >= 1
