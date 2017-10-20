from unittest.mock import MagicMock, call
import asyncio
import os
import pytest
import shutil
import tempfile

import hobbler


@pytest.fixture
def fake_tarpit_dir():
    tempdir = tempfile.mkdtemp()
    open(os.path.join(tempdir, 'tasks'), 'w').close()
    yield tempdir
    shutil.rmtree(tempdir)


def _add_to_tarpit(pid, tarpit_dir):
    with open(os.path.join(tarpit_dir, 'tasks'), 'a') as f:
        f.write(str(pid) + '\n')


@pytest.mark.asyncio
async def test_get_all_pids(fake_tarpit_dir):
    _add_to_tarpit(123, fake_tarpit_dir)
    _add_to_tarpit(124, fake_tarpit_dir)
    pids = await hobbler.get_all_pids(fake_tarpit_dir)
    assert pids == {123, 124}


@pytest.mark.asyncio
async def test_get_all_pids_when_empty(fake_tarpit_dir):
    pids = await hobbler.get_all_pids(fake_tarpit_dir)
    assert pids == set()


@pytest.mark.asyncio
async def test_update_processes_to_hobble_adds_to_queue(fake_tarpit_dir):
    queue = asyncio.queues.LifoQueue()
    _add_to_tarpit(1, fake_tarpit_dir)
    _add_to_tarpit(2, fake_tarpit_dir)
    await hobbler.update_processes_to_hobble(fake_tarpit_dir, queue)
    latest_pids = queue.get_nowait()
    assert latest_pids == {1, 2}


@pytest.fixture
def mocked_pid_ops(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(hobbler, 'pause_process', mock.pause_process)
    monkeypatch.setattr(hobbler, 'restart_process', mock.restart_process)
    return mock



@pytest.mark.asyncio
async def test_hobble_processes_does_all_pids_on_queue(
    fake_tarpit_dir, mocked_pid_ops
):
    await hobbler.hobble_processes([10, 11, 12])

    assert mocked_pid_ops.pause_process.call_args_list == [
        call(10), call(11), call(12)
    ]
    assert mocked_pid_ops.pause_process.call_args_list == [
        call(10), call(11), call(12)
    ]



@pytest.mark.asyncio
async def test_hobble_processes_does_all_pauses_then_all_restarts(
    fake_tarpit_dir, mocked_pid_ops
):

    await hobbler.hobble_processes([10, 11])
    assert mocked_pid_ops.method_calls == [
        call.pause_process(10),
        call.pause_process(11),
        call.restart_process(10),
        call.restart_process(11),
    ]


@pytest.mark.asyncio
async def test_hobble_processes_forever_for_nonempty_queue(
    monkeypatch, mocked_pid_ops
):
    mocked_pid_ops.pause_process.side_effect = Exception('exit loop')
    queue = asyncio.queues.LifoQueue()
    await queue.put([3])
    with pytest.raises(Exception) as e:
        await hobbler.hobble_processes_forever(queue)
    assert 'exit loop' in str(e)

