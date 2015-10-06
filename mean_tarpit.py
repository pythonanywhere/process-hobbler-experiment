#!/usr/bin/python3.4
"""Mean tarpit, a process hobbler

Usage:
  mean_tarpit.py <tarpit_cgroup_dir> [--testing]

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



@asyncio.coroutine
def get_pids(tarpit_cgroup_dir):
    with open(os.path.join(tarpit_cgroup_dir, 'tasks')) as f:
        return f.readlines()


@asyncio.coroutine
def hobble_process(pid, loop):
    print('hobbling pid', pid)
    pid = int(pid)
    process = psutil.Process(pid)
    while True:
        try:
            os.kill(pid, signal.SIGSTOP)
            children = yield from loop.run_in_executor(
                loop.threadpool,
                lambda: process.children(recursive=True)
            )
            for child in children:
                print('hobbling child pid', child.pid)
                os.kill(child.pid, signal.SIGSTOP)
            yield from asyncio.sleep(0.25)
            for child in reversed(children):
                os.kill(child.pid, signal.SIGCONT)
            os.kill(pid, signal.SIGCONT)
            yield from asyncio.sleep(0.01)

        except ProcessLookupError:
            print('process {} no longer exists'.format(pid))
            break


@asyncio.coroutine
def hobble_current_processes(loop, already_hobbled, tarpit_cgroup_dir):
    print('getting latest process list')
    pids = yield from get_pids(tarpit_cgroup_dir)
    for pid in pids:
        if pid in already_hobbled:
            continue
        already_hobbled.add(pid)
        loop.create_task(
            hobble_process(pid, loop)
        )
    print('now hobbling {} processes'.format(len(already_hobbled)))


@asyncio.coroutine
def hobble_processes_forever(loop, tarpit_cgroup_dir, tarpit_update_pause):
    already_hobbled = set()
    while True:
        print('hobbling...', flush=True)
        yield from hobble_current_processes(loop, already_hobbled, tarpit_cgroup_dir)
        yield from asyncio.sleep(tarpit_update_pause)


def main(tarpit_cgroup_dir, tarpit_update_pause):
    print('Starting mean tarpit')
    loop = asyncio.get_event_loop()
    if not hasattr(loop, 'create_task'):  # was added in 3.4.2
        loop.create_task = asyncio.async
    loop.threadpool = ThreadPoolExecutor(max_workers=20)
    loop.create_task(
        hobble_processes_forever(loop, tarpit_cgroup_dir, tarpit_update_pause)
    )
    loop.run_forever()
    loop.close()


if __name__ == '__main__':
    args = docopt(__doc__)
    tarpit = args['<tarpit_cgroup_dir>']
    assert os.path.exists(os.path.join(tarpit, 'tasks'))
    pause = 2 if not args.get('--testing') else 0.3
    main(tarpit, pause)

