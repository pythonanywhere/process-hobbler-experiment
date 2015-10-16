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
from collections import namedtuple
from docopt import docopt
import os
import psutil
import signal
import time
import threading

HOBBLING = 'hobbling pid {}'
HOBBLING_CHILD = 'hobbling child pid {}'
HOBBLED_PROCESS_DIED = 'hobbled process {} no longer exists'


def get_all_pids(cgroup_dir):
    with open(os.path.join(cgroup_dir, 'tasks')) as f:
        for line in f.readlines():
            try:
                yield int(line)
            except ValueError:
                pass

TopLevelProcess = namedtuple('TopLevelProcess', 'pid children')


def get_top_level_processes(cgroup_dir):
    all_pids = set(get_all_pids(cgroup_dir))
    top_levels = []
    for pid in all_pids:
        try:
            process = psutil.Process(pid)
            if process.parent().pid not in all_pids:
                top_levels.append(TopLevelProcess(
                    pid,
                    list(c.pid for c in process.children(recursive=True))
                ))
        except psutil.NoSuchProcess:
            print('task list process {} no longer exists'.format(pid))
    return top_levels


def hobble_process_tree(parent):
    print(HOBBLING.format(parent.pid))
    while True:
        try:
            os.kill(parent.pid, signal.SIGSTOP)
            for child in parent.children:
                print(HOBBLING_CHILD.format(child))
                os.kill(child, signal.SIGSTOP)
            time.sleep(0.25)
            for child in reversed(parent.children):
                os.kill(child, signal.SIGCONT)
            os.kill(parent.pid, signal.SIGCONT)
            time.sleep(0.01)

        except ProcessLookupError:
            print(HOBBLED_PROCESS_DIED.format(parent.pid))
            break


def hobble_current_processes(already_hobbled, cgroup_dir):
    print('getting latest process list')
    parents = get_top_level_processes(cgroup_dir)
    for parent in parents:
        if parent.pid in already_hobbled:
            continue
        already_hobbled.add(parent.pid)
        threading.Thread(target=lambda: hobble_process_tree(parent)).start()
    print('now hobbling {} processes'.format(len(already_hobbled)))


def hobble_processes_forever(cgroup_dir, tarpit_update_pause):
    already_hobbled = set()
    while True:
        print('hobbling...', flush=True)
        threading.Thread(
            target=lambda: hobble_current_processes(already_hobbled, cgroup_dir)
        ).start()
        time.sleep(tarpit_update_pause)


def main(cgroup_dir, tarpit_update_pause):
    print('Starting process hobbler')
    hobble_processes_forever(cgroup_dir, tarpit_update_pause)


if __name__ == '__main__':
    args = docopt(__doc__)
    cgroup = args['<cgroup_dir>']  # doesnt have to be a real cgroup, just needs to contain a file called "tasks" with a list of pids in it
    assert os.path.exists(os.path.join(cgroup, 'tasks'))
    pause = 2 if not args.get('--testing') else 0.3
    main(cgroup, pause)

