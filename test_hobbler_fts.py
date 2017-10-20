import os
import psutil
import pytest
import subprocess
import time

import hobbler


def _add_to_tarpit(pid, tarpit_dir):
    with open(os.path.join(tarpit_dir, 'tasks'), 'a') as f:
        f.write(str(pid) + '\n')


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



def test_spots_process(fake_tarpit_dir, hobbler_process):
    sleeper = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    pid = sleeper.pid
    _add_to_tarpit(pid, fake_tarpit_dir)
    lines = []
    for _ in range(10):
        line = hobbler_process.stdout.readline().strip()
        print(line)
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
        print(line)
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
    hobbler_process.stdout.read()
    time.sleep(1)

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

