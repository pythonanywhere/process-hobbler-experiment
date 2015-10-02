#!/usr/bin/python3.4
import asyncio
import os
import signal
import sys


@asyncio.coroutine
def get_pids(tarpit_cgroup_dir):
    with open(os.path.join(tarpit_cgroup_dir, 'tasks')) as f:
        return f.readlines()


@asyncio.coroutine
def hobble_process(pid):
    print('hobbling pid', pid)
    pid = int(pid)
    while True:
        try:
            os.kill(pid, signal.SIGSTOP)
            yield from asyncio.sleep(0.2)
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
            hobble_process(pid)
        )
    print('now hobbling {} processes'.format(len(already_hobbled)))


@asyncio.coroutine
def hobble_processes_forever(loop, tarpit_cgroup_dir):
    already_hobbled = set()
    while True:
        print('hobbling current processes')
        yield from hobble_current_processes(loop, already_hobbled, tarpit_cgroup_dir)
        yield from asyncio.sleep(2)


def main(tarpit_cgroup_dir):
    loop = asyncio.get_event_loop()
    loop.create_task(
        hobble_processes_forever(loop, tarpit_cgroup_dir)
    )
    loop.run_forever()
    loop.close()


if __name__ == '__main__':
    if sys.argv[-1].startswith('/'):
        tarpit = sys.argv[-1]
    else:
        tarpit = '/mnt/cgroups/cpu/user_types/tarpit'
    main(tarpit)

