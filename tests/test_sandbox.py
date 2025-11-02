import multiprocessing
import time

from chronix_bot.cogs.owner import sandbox


def test_runner_simple():
    parent, child = multiprocessing.Pipe()
    p = multiprocessing.Process(target=sandbox._runner, args=("print('hello')", child))
    p.start()
    p.join(2)
    assert not p.is_alive()
    assert parent.poll()
    ok, out = parent.recv()
    assert ok is True
    assert "hello" in out
