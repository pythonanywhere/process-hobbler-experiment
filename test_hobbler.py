import os
import inspect
import psutil
import pytest
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



def _get_tarpitter_process(fake_tarpit_dir, testing):
    command = ['python3.4', hobbler.__file__, fake_tarpit_dir]
    if testing:
        command.append('--testing')
    return subprocess.Popen(
        command, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
        stderr=subprocess.STDOUT, universal_newlines=True
    )

@pytest.yield_fixture
def tarpitter_subprocess(fake_tarpit_dir):
    process = _get_tarpitter_process(fake_tarpit_dir, testing=True)
    first_line = process.stdout.readline()
    if 'Traceback' in first_line:
        assert False, process.stdout.read()
    yield process
    process.kill()
    print('full hobbler process output:')
    print(process.stdout.read())


@pytest.yield_fixture
def nontesting_tarpitter_subprocess(fake_tarpit_dir):
    process = _get_tarpitter_process(fake_tarpit_dir, testing=False)
    first_line = process.stdout.readline()
    if 'Traceback' in first_line:
        assert False, process.stdout.read()
    yield process
    process.kill()
    print('full hobbler process output:')
    print(process.stdout.read())



@pytest.mark.slowtest
def test_tarpit_process_is_slow(fake_tarpit_dir, tarpitter_subprocess):
    print('my pid', os.getpid())
    timer = "import time; time.sleep(0.4); start = time.time(); list(range(int(1e6))); print(time.time() - start)"
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
    assert normal * 20 < slow
    assert normal * 100 > slow



def _add_to_tarpit(pid, tarpit_dir):
    with open(os.path.join(tarpit_dir, 'tasks'), 'a') as f:
        f.write(str(pid) + '\n')


def test_spots_process(fake_tarpit_dir, tarpitter_subprocess):
    sleeper = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    pid = sleeper.pid
    _add_to_tarpit(pid, fake_tarpit_dir)
    lines = []
    for _ in range(10):
        line = tarpitter_subprocess.stdout.readline().strip()
        lines.append(line)
        if line == hobbler.HOBBLING.format(pid):
            break
    else:
        assert False, 'never hobbled pid {}. output was:\n{}'.format(pid, ''.join(lines))
    sleeper.kill()


def test_spots_multiple_processes(fake_tarpit_dir, tarpitter_subprocess):
    sleeper1 = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    sleeper2 = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    pid1 = str(sleeper1.pid)
    pid2 = str(sleeper2.pid)
    _add_to_tarpit(pid1, fake_tarpit_dir)
    _add_to_tarpit(pid2, fake_tarpit_dir)

    lines = []
    for _ in range(20):
        line = tarpitter_subprocess.stdout.readline().strip()
        lines.append(line)

    assert hobbler.HOBBLING.format(pid1) in lines
    assert hobbler.HOBBLING.format(pid2) in lines

    sleeper1.kill()
    sleeper2.kill()


def test_doesnt_hobble_any_old_process(fake_tarpit_dir, tarpitter_subprocess):
    sleeper = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    pid = str(sleeper.pid)
    lines = []
    for _ in range(10):
        line = tarpitter_subprocess.stdout.readline().strip()
        lines.append(line)

    assert hobbler.HOBBLING.format(pid) not in lines
    sleeper.kill()


def test_stops_hobbling_dead_processes(fake_tarpit_dir, tarpitter_subprocess):
    p = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    pid = str(p.pid)
    _add_to_tarpit(pid, fake_tarpit_dir)

    hobbling = hobbler.HOBBLING.format(pid)
    stopped = hobbler.HOBBLED_PROCESS_DIED.format(pid)

    lines = []
    for _ in range(10):
        line = tarpitter_subprocess.stdout.readline().strip()
        lines.append(line)
        if line == hobbling:
            break
    else:
        assert False, 'never hobbled pid {}. output was:\n{}'.format(pid, ''.join(lines))

    p.kill()
    p.wait()

    for _ in range(10):
        line = tarpitter_subprocess.stdout.readline().strip()
        lines.append(line)

    print('\n'.join(lines))
    assert hobbling in lines
    assert stopped in lines
    assert lines.count(hobbling) == 1
    assert lines.count(stopped) == 1
    assert lines.index(hobbling) < lines.index(stopped)


def forker():
    import os
    import time
    for i in range(3):
        print(os.getpid(), flush=True)
        os.fork()
    time.sleep(4)



def test_hobbles_children(fake_tarpit_dir, tarpitter_subprocess):
    tf = tempfile.NamedTemporaryFile(delete=False)
    with tf:
        tf.write(inspect.getsource(forker).encode('utf8'))
        tf.write('\nforker()\n'.encode('utf8'))
    p = subprocess.Popen(
        ['python3', tf.name],
        universal_newlines=True, stdout=subprocess.PIPE
    )
    _add_to_tarpit(p.pid, fake_tarpit_dir)

    first_pid = p.stdout.readline().strip()
    for _ in range(5):
        next_pid = p.stdout.readline().strip()
        if next_pid != first_pid:
            break

    time.sleep(0.5)  # make sure they've all started
    children = psutil.Process(p.pid).children(recursive=True)
    assert len(children) > 4

    lines = []
    for _ in range(20):
        line = tarpitter_subprocess.stdout.readline().strip()
        lines.append(line)

    for c in children:
        assert hobbler.HOBBLING_CHILD.format(c.pid) in lines

    p.kill()
    p.wait()
    os.remove(tf.name)


@pytest.mark.slowtest
def test_lots_of_processes(fake_tarpit_dir, nontesting_tarpitter_subprocess):
    start_times = psutil.Process(nontesting_tarpitter_subprocess.pid).cpu_times()
    print('start times', start_times)
    procs = []
    for i in range(100):
        p = subprocess.Popen(['sleep', '100'], universal_newlines=True)
        _add_to_tarpit(p.pid, fake_tarpit_dir)
        procs.append(p)

    time.sleep(7) # time for 3 iterations

    end_times = psutil.Process(nontesting_tarpitter_subprocess.pid).cpu_times()
    print('end times', end_times)

    assert end_times.user > start_times.user
    assert end_times.system > start_times.system

    psutil.Process(nontesting_tarpitter_subprocess.pid).cpu_percent(interval=0.1)  # warm-up
    assert psutil.Process(nontesting_tarpitter_subprocess.pid).cpu_percent(interval=2) < 10


def test_get_top_level_processes_returns_list_of_parents_and_with_chidren():
    tf = tempfile.NamedTemporaryFile(delete=False)
    with tf:
        tf.write(inspect.getsource(forker).encode('utf8'))
        tf.write('\nforker()\n'.encode('utf8'))

    p1 = subprocess.Popen(
        ['python3', tf.name],
        universal_newlines=True, stdout=subprocess.PIPE
    )
    p2 = subprocess.Popen(
        ['python3', tf.name],
        universal_newlines=True, stdout=subprocess.PIPE
    )
    time.sleep(1)

    tempdir = tempfile.mkdtemp()
    p1_children = [c.pid for c in psutil.Process(p1.pid).children(recursive=True)]
    p2_children = [c.pid for c in psutil.Process(p2.pid).children(recursive=True)]
    with open(os.path.join(tempdir, 'tasks'), 'a') as f:
        f.write(str(p1.pid) + '\n')
        f.write(str(p2.pid) + '\n')

    for p in p1_children + p2_children:
        with open(os.path.join(tempdir, 'tasks'), 'a') as f:
            f.write(str(p) + '\n')

    print(subprocess.check_output('ps auxf | grep python', shell=True).decode('utf8'))

    parents = list(hobbler.get_top_level_processes(tempdir))
    assert len(parents) == 2
    parent1, parent2 = parents
    assert {parent1.pid, parent2.pid} == {p1.pid, p2.pid}
    if parent1.pid == p1.pid:
        assert parent2.pid == p2.pid
        assert parent1.children == p1_children
        assert parent2.children == p2_children
    else:
        assert parent1.pid == p2.pid
        assert parent1.children == p2_children
        assert parent2.children == p1_children

