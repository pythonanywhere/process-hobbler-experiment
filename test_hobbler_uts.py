from unittest.mock import call
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


@pytest.mark.asyncio
async def test_get_all_pids(fake_tarpit_pid, fake_tarpit_dir):
    fake_tarpit_pid(123)
    fake_tarpit_pid(124)
    pids = await hobbler.get_all_pids(fake_tarpit_dir)
    assert pids == {123, 124}


@pytest.mark.asyncio
async def test_get_all_pids_when_empty(fake_tarpit_dir):
    pids = await hobbler.get_all_pids(fake_tarpit_dir)
    assert pids == set()


@pytest.mark.asyncio
async def test_update_processes_to_hobble_adds_to_queue(
    fake_tarpit_pid, fake_tarpit_dir
):
    queue = asyncio.queues.LifoQueue()
    fake_tarpit_pid(1)
    fake_tarpit_pid(2)
    await hobbler.update_processes_to_hobble(fake_tarpit_dir, queue)
    latest_pids = queue.get_nowait()
    assert latest_pids == {1, 2}




@pytest.mark.asyncio
async def test_hobble_processes_does_all_pids_on_queue(
    fake_tarpit_dir, mocked_pid_ops
):
    await hobbler.hobble_processes([10, 11, 12], test_mode=False)

    assert mocked_pid_ops.pause_process.call_args_list == [
        call(10), call(11), call(12)
    ]
    assert mocked_pid_ops.pause_process.call_args_list == [
        call(10), call(11), call(12)
    ]

@pytest.mark.asyncio
async def test_hobble_processes_prints_in_test_mode(
    fake_tarpit_dir, mocked_pid_ops, capsys
):
    pids = [10, 11, 12]
    await hobbler.hobble_processes(pids, test_mode=False)
    assert hobbler.HOBBLING_PIDS_MSG.format(pids) not in capsys.readouterr()[0]
    await hobbler.hobble_processes(pids, test_mode=True)
    assert hobbler.HOBBLING_PIDS_MSG.format(pids) in capsys.readouterr()[0]



@pytest.mark.asyncio
async def test_hobble_processes_does_all_pauses_then_all_restarts(
    fake_tarpit_dir, mocked_pid_ops
):

    await hobbler.hobble_processes([10, 11], test_mode=True)
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
        await hobbler.hobble_processes_forever(queue, test_mode=False)
    assert 'exit loop' in str(e)

