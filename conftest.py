import os
import pytest
import shutil
import subprocess
import tempfile

import hobbler


@pytest.fixture
def fake_tarpit_dir():
    tempdir = tempfile.mkdtemp()
    open(os.path.join(tempdir, 'tasks'), 'w').close()
    yield tempdir
    shutil.rmtree(tempdir)


@pytest.fixture
def fake_tarpit_pid(fake_tarpit_dir):
    def add_pid_to_fake_tarpit(pid):
        with open(os.path.join(fake_tarpit_dir, 'tasks'), 'a') as f:
            f.write(str(pid) + '\n')
    return add_pid_to_fake_tarpit


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


@pytest.fixture
def hobbler_process(fake_tarpit_dir):
    process = _get_hobbler_process(fake_tarpit_dir, testing=True)
    yield process
    process.kill()
    print('full hobbler process output:')
    print(process.stdout.read())


@pytest.fixture
def nontesting_hobbler_process(fake_tarpit_dir):
    process = _get_hobbler_process(fake_tarpit_dir, testing=False)
    yield process
    process.kill()
    print('full hobbler process output:')
    print(process.stdout.read())

