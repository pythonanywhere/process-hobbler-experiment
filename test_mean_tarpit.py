import os
import pytest
import shutil
import subprocess
import tempfile
import threading
import time


from . import mean_tarpit

@pytest.yield_fixture
def fake_tarpit_dir():
    tempdir = tempfile.mkdtemp()
    open(os.path.join(tempdir, 'tasks'), 'w').close()
    yield tempdir
    shutil.rmtree(tempdir)


@pytest.yield_fixture
def mean_tarpitter_in_subprocess(fake_tarpit_dir):
    process = subprocess.Popen(
        ['python3', mean_tarpit.__file__, fake_tarpit_dir, '--testing'],
        stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True
    )
    first_line = process.stdout.readline()
    if 'Traceback' in first_line:
        assert False, process.stdout.read()
    yield process
    process.kill()
    print('full mean tarpit process output:')
    print(process.stdout.read())



@pytest.mark.slowtest
def test_tarpit_process_is_slow(fake_tarpit_dir, mean_tarpitter_in_subprocess):
    print('my pid', os.getpid())
    timer =  "import time; time.sleep(0.4); start = time.time(); list(range(int(1e6))); print(time.time() - start)"
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


def test_spots_process(fake_tarpit_dir, mean_tarpitter_in_subprocess):
    sleeper = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    pid = str(sleeper.pid)
    with open(os.path.join(fake_tarpit_dir, 'tasks'), 'w') as f:
        f.write(pid)
    lines = []
    for _ in range(10):
        line = mean_tarpitter_in_subprocess.stdout.readline().strip()
        lines.append(line)
        if line == 'hobbling pid {}'.format(pid):
            break
    else:
        assert False, 'never hobbled pid {}. output was:\n{}'.format(pid, ''.join(lines))
    sleeper.kill()


def test_spots_multiple_processes(fake_tarpit_dir, mean_tarpitter_in_subprocess):
    sleeper1 = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    pid1 = str(sleeper1.pid)
    sleeper2 = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    pid2 = str(sleeper2.pid)
    with open(os.path.join(fake_tarpit_dir, 'tasks'), 'w') as f:
        f.write(pid1 + '\n')
        f.write(pid2 + '\n')
    lines = []

    for _ in range(20):
        line = mean_tarpitter_in_subprocess.stdout.readline().strip()
        lines.append(line)

    assert 'hobbling pid {}'.format(pid1) in lines
    assert 'hobbling pid {}'.format(pid2) in lines

    sleeper1.kill()
    sleeper2.kill()


def test_doesnt_hobble_any_old_process(fake_tarpit_dir, mean_tarpitter_in_subprocess):
    sleeper = subprocess.Popen(['sleep', '10'], universal_newlines=True)
    pid = str(sleeper.pid)
    lines = []
    for _ in range(10):
        line = mean_tarpitter_in_subprocess.stdout.readline().strip()
        lines.append(line)

    assert 'hobbling pid {}'.format(pid) not in lines

    sleeper.kill()

