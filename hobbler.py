#!/usr/bin/python3.4
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
from concurrent.futures import ThreadPoolExecutor
from docopt import docopt
import os
import psutil
import signal



def get_all_pids(cgroup_dir):
    with open(os.path.join(cgroup_dir, 'tasks')) as f:
        for line in f.readlines():
            try:
                yield int(line)
            except ValueError:
                pass


def get_pids(cgroup_dir):
    all_pids = set(get_all_pids(cgroup_dir))
    parents = set()
    for p in all_pids:
        proc = psutil.Process(p)
        if proc.parent().pid not in all_pids:
            parents.add(proc)
    for p in parents:
        p.children = p.children(recursive=True)
    print(all_pids)
    print(parents)
    return parents


@asyncio.coroutine
def hobble_process(pid, loop):
    print('hobbling pid', pid)
    pid = int(pid)
    process = psutil.Process(pid)
    while True:
        try:
            os.kill(pid, signal.SIGSTOP)
            # children = yield from loop.run_in_executor(
            #     loop.threadpool,
            #     lambda: process.children(recursive=True)
            # )
            # for child in children:
            #     print('hobbling child pid', child.pid)
            #     os.kill(child.pid, signal.SIGSTOP)
            yield from asyncio.sleep(0.25)
            # for child in reversed(children):
            #     os.kill(child.pid, signal.SIGCONT)
            os.kill(pid, signal.SIGCONT)
            yield from asyncio.sleep(0.01)

        except ProcessLookupError:
            print('process {} no longer exists'.format(pid))
            break


@asyncio.coroutine
def hobble_current_processes(loop, already_hobbled, cgroup_dir):
    print('getting latest process list')
    pids = get_pids(cgroup_dir)
    for pid in pids:
        if pid in already_hobbled:
            continue
        already_hobbled.add(pid)
        loop.create_task(
            hobble_process(pid, loop)
        )
    print('now hobbling {} processes'.format(len(already_hobbled)))


@asyncio.coroutine
def hobble_processes_forever(loop, cgroup_dir, tarpit_update_pause):
    already_hobbled = set()
    while True:
        print('hobbling...', flush=True)
        yield from hobble_current_processes(loop, already_hobbled, cgroup_dir)
        yield from asyncio.sleep(tarpit_update_pause)


def main(cgroup_dir, tarpit_update_pause):
    print('Starting process hobbler')
    loop = asyncio.get_event_loop()
    if not hasattr(loop, 'create_task'):  # was added in 3.4.2
        loop.create_task = asyncio.async
    loop.threadpool = ThreadPoolExecutor(max_workers=20)
    loop.create_task(
        hobble_processes_forever(loop, cgroup_dir, tarpit_update_pause)
    )
    loop.run_forever()
    loop.close()


if __name__ == '__main__':
    args = docopt(__doc__)
    cgroup = args['<cgroup_dir>']  # doesnt have to be a real cgroup, just needs to contain a file called "tasks" with a list of pids in it
    assert os.path.exists(os.path.join(cgroup, 'tasks'))
    pause = 2 if not args.get('--testing') else 0.3
    main(cgroup, pause)

