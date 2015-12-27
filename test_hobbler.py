import os
import inspect
import psutil
import pytest
import random
import shutil
import subprocess
import tempfile
import time


import hobbler

@pytest.yield_fixture
def fake_tarpit_dir():
    tempdir = tempfile.mkdtemp()
    open(os.path.join(tempdir, 'tasks'), 'w').close()
    yield tempdir
    shutil.rmtree(tempdir)



def _get_hobbler_process(fake_tarpit_dir, testing):
    command = [hobbler.__file__, fake_tarpit_dir]
    if testing:
        command.append('--testing')
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
        stderr=subprocess.STDOUT, universal_newlines=True
    )
    first_line = process.stdout.readline()
    if 'Traceback' in first_line:
        assert False, process.stdout.read()
    return process


@pytest.yield_fixture
def hobbler_process(fake_tarpit_dir):
    process = _get_hobbler_process(fake_tarpit_dir, testing=True)
    yield process
    process.kill()
    print('full hobbler process output:')
    print(process.stdout.read())


@pytest.yield_fixture
def nontesting_hobbler_process(fake_tarpit_dir):
    process = _get_hobbler_process(fake_tarpit_dir, testing=False)
    yield process
    process.kill()
    print('full hobbler process output:')
    print(process.stdout.read())


@pytest.mark.slowtest
def test_tarpit_process_is_slow(fake_tarpit_dir, hobbler_process):
    print('my pid', os.getpid())
    timer = "; ".join([
        "import time",
        "time.sleep(0.4)",  # give hobbler a chance to spot us
        "start = time.time()",
        "list(range(int(1e6)))",  # do some work
        "print(time.time() - start)",
    ])
    normal = subprocess.check_output(['python', '-c', timer], universal_newlines=True)
    normal = float(normal)
    print("normal", normal)
    slow = subprocess.check_output([
        'python', '-c',
        "import os; open('{}/tasks', 'w').write(str(os.getpid())); ".format(fake_tarpit_dir) + timer
    ], universal_newlines=True)
    slow = float(slow)
    print("slow", slow)
    assert normal < slow
    assert normal * 10 < slow
    assert normal * 100 > slow



def _add_to_tarpit(pid, tarpit_dir):
    with open(os.path.join(tarpit_dir, 'tasks'), 'a') as f:
        f.write(str(pid) + '\n')


def test_spots_process(fake_tarpit_dir, hobbler_process):
    sleeper = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    pid = sleeper.pid
    _add_to_tarpit(pid, fake_tarpit_dir)
    lines = []
    for _ in range(10):
        line = hobbler_process.stdout.readline().strip()
        lines.append(line)
        if line == hobbler.HOBBLING.format(pid):
            break
    else:
        assert False, 'never hobbled pid {}. output was:\n{}'.format(pid, ''.join(lines))
    sleeper.kill()


def test_spots_multiple_processes(fake_tarpit_dir, hobbler_process):
    sleeper1 = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    sleeper2 = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    pid1 = str(sleeper1.pid)
    pid2 = str(sleeper2.pid)
    _add_to_tarpit(pid1, fake_tarpit_dir)
    _add_to_tarpit(pid2, fake_tarpit_dir)

    lines = []
    for _ in range(20):
        line = hobbler_process.stdout.readline().strip()
        lines.append(line)

    assert hobbler.HOBBLING.format(pid1) in lines
    assert hobbler.HOBBLING.format(pid2) in lines

    sleeper1.kill()
    sleeper2.kill()


def test_doesnt_hobble_any_old_process(fake_tarpit_dir, hobbler_process):
    sleeper = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    pid = str(sleeper.pid)
    lines = []
    for _ in range(10):
        line = hobbler_process.stdout.readline().strip()
        lines.append(line)

    assert hobbler.HOBBLING.format(pid) not in lines
    sleeper.kill()


def test_stops_hobbling_dead_processes(fake_tarpit_dir, hobbler_process):
    p = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    pid = str(p.pid)
    _add_to_tarpit(pid, fake_tarpit_dir)

    hobbling = hobbler.HOBBLING.format(pid)
    stopped = hobbler.HOBBLED_PROCESS_DIED.format(pid)

    lines = []
    for _ in range(10):
        line = hobbler_process.stdout.readline().strip()
        lines.append(line)
        if line == hobbling:
            break
    else:
        assert False, 'never hobbled pid {}. output was:\n{}'.format(pid, ''.join(lines))

    p.kill()
    p.wait()

    for _ in range(10):
        line = hobbler_process.stdout.readline().strip()
        lines.append(line)

    print('\n'.join(lines))
    assert hobbling in lines
    assert stopped in lines
    assert lines.count(hobbling) == 1
    assert lines.count(stopped) == 1
    assert lines.index(hobbling) < lines.index(stopped)


def _forker():
    import os
    import time
    for i in range(3):
        print(os.getpid(), flush=True)
        os.fork()
    time.sleep(4)


def _get_forkey_process_tree():
    tf = tempfile.NamedTemporaryFile(delete=False)
    with tf:
        tf.write(inspect.getsource(_forker).encode('utf8'))
        tf.write('\n_forker()\n'.encode('utf8'))
    toplevel = subprocess.Popen(
        ['python3', tf.name],
        universal_newlines=True, stdout=subprocess.PIPE
    )
    while len(psutil.Process(toplevel.pid).children(recursive=True)) < 7:
        time.sleep(0.1)
    os.remove(tf.name)
    return toplevel



def test_hobbles_children(fake_tarpit_dir, hobbler_process):
    forker = _get_forkey_process_tree()
    _add_to_tarpit(forker.pid, fake_tarpit_dir)
    children = psutil.Process(forker.pid).children(recursive=True)

    lines = []
    for _ in range(20):
        line = hobbler_process.stdout.readline().strip()
        lines.append(line)

    for c in children:
        assert hobbler.HOBBLING_CHILD.format(c.pid) in lines

    forker.kill()
    forker.wait()


@pytest.mark.slowtest
def test_lots_of_processes(fake_tarpit_dir, nontesting_hobbler_process):
    start_times = psutil.Process(nontesting_hobbler_process.pid).cpu_times()
    print('start times', start_times)
    procs = []
    for i in range(200):
        p = subprocess.Popen(['sleep', '100'], universal_newlines=True)
        _add_to_tarpit(p.pid, fake_tarpit_dir)
        procs.append(p)

    time.sleep(7) # time for 3 iterations

    end_times = psutil.Process(nontesting_hobbler_process.pid).cpu_times()
    print('end times', end_times)

    assert end_times.user > start_times.user
    assert end_times.system > start_times.system

    psutil.Process(nontesting_hobbler_process.pid).cpu_percent(interval=0.1)  # warm-up
    assert psutil.Process(nontesting_hobbler_process.pid).cpu_percent(interval=2) < 10


def test_get_top_level_processes_returns_list_of_parents_with_children(fake_tarpit_dir):
    forker1 = _get_forkey_process_tree()
    forker2 = _get_forkey_process_tree()
    print(subprocess.check_output('ps auxf | grep "python3 /tmp"', shell=True).decode('utf8'))

    forker1_children = [c.pid for c in psutil.Process(forker1.pid).children(recursive=True)]
    forker2_children = [c.pid for c in psutil.Process(forker2.pid).children(recursive=True)]
    all_pids = [forker1.pid, forker2.pid] + forker1_children + forker2_children
    random.shuffle(all_pids)
    for pid in all_pids:
        _add_to_tarpit(pid, fake_tarpit_dir)

    parents = list(hobbler.get_top_level_processes(fake_tarpit_dir))

    assert len(parents) == 2

    assert set([parents[0].pid, parents[1].pid]) == {forker1.pid, forker2.pid}
    if parents[0].pid == forker1.pid:
        parent1, parent2 = parents
    else:
        parent2, parent1 = parents

    assert parent1.pid == forker1.pid
    assert parent2.pid == forker2.pid
    assert parent1.children == forker1_children
    assert parent2.children == forker2_children


import asyncio
import signal
from unittest.mock import call, patch

@patch('hobbler.os.kill')
def test_hobbles_process_tree_in_correct_order(mock_kill):
    parent = hobbler.TopLevelProcess(
        'top pid', ['child1', 'child2', 'child3']
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        hobbler.stop_and_restart(parent)
    )
    assert mock_kill.call_args_list == [
        call('top pid', signal.SIGSTOP),
        call('child1', signal.SIGSTOP),
        call('child2', signal.SIGSTOP),
        call('child3', signal.SIGSTOP),
        call('child3', signal.SIGCONT),
        call('child2', signal.SIGCONT),
        call('child1', signal.SIGCONT),
        call('top pid', signal.SIGCONT),
    ]


