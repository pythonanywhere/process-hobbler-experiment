#!/usr/bin/env python
"""A process "hobbler" that uses SIGSTOP and SIGCONT to pause processes for 90%
of the time, allowing them only a few hundredths of a second of execution time
in any given second.

Usage:
  hobbler.py <cgroup_dir> [--testing]

<cgroup_dir> is assumed to be a cgroup directory, but it can be any directory
as long as it contains a file called "tasks" with a list of pids in it.

Options:
  -h --help             Show this screen.
  --testing             Testing mode (faster loop)
"""
import asyncio
import aiofiles
from docopt import docopt
import os
import signal

HOBBLED_PROCESS_DIED = 'hobbled process {} no longer exists'
HOBBLING_PIDS_MSG = 'hobbling pids: {}'


async def get_all_pids(cgroup_dir):
    pids = set()
    async with aiofiles.open(os.path.join(cgroup_dir, 'tasks')) as f:
        async for line in f:
            try:
                pids.add(int(line))
            except ValueError:
                pass
    return pids


def _empty_queue(queue):
    while True:
        try:
            queue.get_nowait()
        except asyncio.queues.QueueEmpty:
            return


async def update_processes_to_hobble(cgroup_dir, queue):
    new_pids = await get_all_pids(cgroup_dir)
    print(f'updating pid list; hobbling {new_pids}', flush=True)
    _empty_queue(queue)
    await queue.put(new_pids)



async def keep_polling_processes_to_hobble(cgroup_dir, queue, tarpit_update_pause):
    while True:
        await update_processes_to_hobble(cgroup_dir, queue)
        await asyncio.sleep(tarpit_update_pause)



def pause_process(pid):
    try:
        os.kill(pid, signal.SIGSTOP)
    except ProcessLookupError:
        print(HOBBLED_PROCESS_DIED.format(pid))


def restart_process(pid):
    try:
        os.kill(pid, signal.SIGCONT)
    except ProcessLookupError:
        print(HOBBLED_PROCESS_DIED.format(pid))



async def hobble_processes(pids, test_mode):
    if test_mode:
        print(HOBBLING_PIDS_MSG.format(pids, flush=True))
    for pid in pids:
        pause_process(pid)
    await asyncio.sleep(0.25)
    for pid in pids:
        restart_process(pid)
    await asyncio.sleep(0.01)




async def hobble_processes_forever(queue, test_mode):
    print('first get on queue')
    to_hobble = await queue.get()
    print('off we go a-hobblin!', to_hobble)
    while True:
        try:
            to_hobble = queue.get_nowait()
            if test_mode:
                print('got new processes to hobble', to_hobble)
        except asyncio.queues.QueueEmpty:
            if test_mode:
                print('sticking with old list of processes', to_hobble)
        await hobble_processes(to_hobble, test_mode)


def main(cgroup_dir, test_mode):
    print('Starting process hobbler', flush=True)
    loop = asyncio.get_event_loop()
    queue = asyncio.queues.LifoQueue()
    tarpit_update_pause = 0.3 if test_mode else 2
    loop.create_task(
        keep_polling_processes_to_hobble(cgroup_dir, queue, tarpit_update_pause)
    )
    loop.create_task(
        hobble_processes_forever(queue, test_mode)
    )
    loop.run_forever()
    loop.close()


if __name__ == '__main__':
    args = docopt(__doc__)
    cgroup = args['<cgroup_dir>']  # doesnt have to be a real cgroup, just needs to contain a file called "tasks" with a list of pids in it
    assert os.path.exists(os.path.join(cgroup, 'tasks'))
    main(cgroup, args.get('--testing'))

