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
def start_main_in_subprocess(fake_tarpit_dir):
    process = subprocess.Popen(
        ['python3', mean_tarpit.__file__, fake_tarpit_dir],
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
def test_tarpit_process_is_slow(fake_tarpit_dir, start_main_in_subprocess):
    print('my pid', os.getpid())
    timer =  "import time; time.sleep(2.1); start = time.time(); list(range(int(1e6))); print(time.time() - start)"
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

