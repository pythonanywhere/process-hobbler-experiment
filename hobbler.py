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

HOBBLING = 'hobbling pid {}'
HOBBLED_PROCESS_DIED = 'hobbled process {} no longer exists'


async def get_all_pids(cgroup_dir):
    async with aiofiles.open(os.path.join(cgroup_dir, 'tasks')) as f:
        async for line in f:
            try:
                yield int(line)
            except ValueError:
                pass

to_hobble = set()

async def update_processes_to_hobble(loop, cgroup_dir, tarpit_update_pause):
    global to_hobble
    while True:
        print('updating pid list', flush=True)
        new_pids = []
        async for pid in get_all_pids(cgroup_dir):
            new_pids.append(pid)
        if not new_pids:
            print('no pids in', cgroup_dir)
        else:
            to_hobble = set(new_pids)
        await asyncio.sleep(tarpit_update_pause)


async def hobble_processes_forever(loop):
    global to_hobble
    print('now hobbling {} processes'.format(len(to_hobble)), flush=True)
    while True:
        for pid in to_hobble:
            try:
                print(HOBBLING.format(pid))
                os.kill(pid, signal.SIGSTOP)
            except ProcessLookupError:
                print(HOBBLED_PROCESS_DIED.format(pid))

        await asyncio.sleep(0.25)

        for pid in to_hobble:
            try:
                os.kill(pid, signal.SIGCONT)
            except ProcessLookupError:
                print(HOBBLED_PROCESS_DIED.format(pid))
        await asyncio.sleep(0.01)


def main(cgroup_dir, tarpit_update_pause):
    print('Starting process hobbler', flush=True)
    loop = asyncio.get_event_loop()
    loop.create_task(
        update_processes_to_hobble(loop, cgroup_dir, tarpit_update_pause)
    )
    loop.create_task(
        hobble_processes_forever(loop)
    )
    loop.run_forever()
    loop.close()


if __name__ == '__main__':
    args = docopt(__doc__)
    cgroup = args['<cgroup_dir>']  # doesnt have to be a real cgroup, just needs to contain a file called "tasks" with a list of pids in it
    assert os.path.exists(os.path.join(cgroup, 'tasks'))
    pause = 2 if not args.get('--testing') else 0.3
    main(cgroup, pause)

