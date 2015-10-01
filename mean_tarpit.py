#!/usr/bin/python3.4
import asyncio
import os
import signal

# TARPIT_CGROUP_DIR = '/mnt/cgroups/cpu.shares/user_types/tarpit'
TARPIT_CGROUP_DIR = '/sys/fs/cgroup/cpu/tarpit'



@asyncio.coroutine
def get_pids():
    with open(os.path.join(TARPIT_CGROUP_DIR, 'tasks')) as f:
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
def hobble_current_processes(loop, already_hobbled):
    print('getting latest process list')
    pids = yield from get_pids()
    for pid in pids:
        if pid in already_hobbled:
            continue
        already_hobbled.add(pid)
        loop.create_task(
            hobble_process(pid)
        )
    print('now hobbling {} processes'.format(len(already_hobbled)))


@asyncio.coroutine
def hobble_processes_forever(loop):
    already_hobbled = set()
    while True:
        print('hobbling current processes')
        yield from hobble_current_processes(loop, already_hobbled)
        yield from asyncio.sleep(2)


def main():
    loop = asyncio.get_event_loop()
    loop.create_task(
        hobble_processes_forever(loop)
    )
    loop.run_forever()
    loop.close()


if __name__ == '__main__':
    main()

