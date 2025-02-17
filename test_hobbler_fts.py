import os
import psutil
import pytest
import subprocess
import time

import hobbler




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
        "import os; open('{}/cgroup.procs', 'w').write(str(os.getpid())); ".format(fake_tarpit_dir) + timer
    ], universal_newlines=True)
    slow = float(slow)
    print("slow", slow)
    assert normal < slow
    assert normal * 10 < slow
    assert normal * 100 > slow



def _wait_for_output(process, expected=None):
    for _ in range(10):
        output = process.output.read()
        if expected and expected in output:
            return output
        time.sleep(0.3)
    if expected:
        assert expected in output
    return output


def test_spots_process(fake_tarpit_pid, hobbler_process):
    sleeper = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    pid = sleeper.pid
    fake_tarpit_pid(pid)
    expected = hobbler.HOBBLING_PIDS_MSG.format({pid})
    _wait_for_output(hobbler_process, expected)
    sleeper.kill()


def test_spots_multiple_processes(fake_tarpit_pid, hobbler_process):
    sleeper1 = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    sleeper2 = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    fake_tarpit_pid(sleeper1.pid)
    fake_tarpit_pid(sleeper2.pid)
    expected = hobbler.HOBBLING_PIDS_MSG.format({sleeper1.pid, sleeper2.pid})
    _wait_for_output(hobbler_process, expected)
    sleeper1.kill()
    sleeper2.kill()



def test_doesnt_hobble_any_old_process(
    fake_tarpit_dir, hobbler_process,
):
    sleeper = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    output = _wait_for_output(hobbler_process)
    assert hobbler.HOBBLING_PIDS_MSG.format({sleeper.pid}) not in output
    sleeper.kill()


def test_stops_hobbling_dead_processes(
    fake_tarpit_pid, empty_fake_tarpit, hobbler_process,
):
    p = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    fake_tarpit_pid(p.pid)

    hobbling = hobbler.HOBBLING_PIDS_MSG.format({p.pid})
    _wait_for_output(hobbler_process, hobbling)
    stopped = hobbler.HOBBLED_PROCESS_DIED.format(p.pid)

    p.kill()
    print('emptying tarpit')
    empty_fake_tarpit()
    p.wait()

    output = _wait_for_output(hobbler_process)
    lines = output.split('\n')
    assert hobbling in lines
    assert stopped in lines
    assert lines.count(hobbling) >= 1
    assert lines.count(stopped) >= 1
    hobbling_lines = [i for i, l in enumerate(lines) if l == hobbling]
    stopping_lines = [i for i, l in enumerate(lines) if l == stopped]
    assert max(hobbling_lines) < max(stopping_lines)


def _forker():
    import os
    import time
    for i in range(3):
        print(os.getpid(), flush=True)
        os.fork()
    time.sleep(4)


@pytest.mark.slowtest
def test_lots_of_processes(fake_tarpit_pid, nontesting_hobbler_process):
    start_times = psutil.Process(nontesting_hobbler_process.pid).cpu_times()
    print('start times', start_times)
    procs = []
    for i in range(200):
        p = subprocess.Popen(['sleep', '100'], universal_newlines=True)
        fake_tarpit_pid(p.pid)
        procs.append(p)

    time.sleep(7) # time for 3 iterations

    end_times = psutil.Process(nontesting_hobbler_process.pid).cpu_times()
    print('end times', end_times)

    assert end_times.user > start_times.user
    assert end_times.system > start_times.system

    psutil.Process(nontesting_hobbler_process.pid).cpu_percent(interval=0.1)  # warm-up
    assert psutil.Process(nontesting_hobbler_process.pid).cpu_percent(interval=2) < 10

