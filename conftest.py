from unittest.mock import MagicMock
import os
import pytest
import shutil
import subprocess
import tempfile

import hobbler


@pytest.fixture
def fake_tarpit_dir():
    tempdir = tempfile.mkdtemp()
    open(os.path.join(tempdir, 'cgroup.procs'), 'w').close()
    yield tempdir
    shutil.rmtree(tempdir)


@pytest.fixture
def fake_tarpit_pid(fake_tarpit_dir):
    def add_pid_to_fake_tarpit(pid):
        with open(os.path.join(fake_tarpit_dir, 'cgroup.procs'), 'a') as f:
            f.write(str(pid) + '\n')
    return add_pid_to_fake_tarpit


@pytest.fixture
def empty_fake_tarpit(fake_tarpit_dir):
    return lambda: open(os.path.join(fake_tarpit_dir, 'cgroup.procs'), 'w').close()


def _get_hobbler_process(fake_tarpit_dir, tmpdir, testing):
    command = [hobbler.__file__, fake_tarpit_dir]
    out = tmpdir.join('out')
    if testing:
        command.append('--testing')
    process = subprocess.Popen(
        command, stdout=out.open('w'), stdin=subprocess.PIPE,
        stderr=subprocess.STDOUT, universal_newlines=True,
    )
    process.output = out
    first_line = process.output.open().readline()
    if 'Traceback' in first_line:
        assert False, process.output.read()
    return process


def _tidy_process(process):
    process.kill()
    print('hobbler output:')
    print(process.output.read())


@pytest.fixture
def hobbler_process(fake_tarpit_dir, tmpdir):
    process = _get_hobbler_process(fake_tarpit_dir, tmpdir, testing=True)
    yield process
    _tidy_process(process)


@pytest.fixture
def nontesting_hobbler_process(fake_tarpit_dir, tmpdir):
    process = _get_hobbler_process(fake_tarpit_dir, tmpdir, testing=False)
    yield process
    _tidy_process(process)


@pytest.fixture
def mocked_pid_ops(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(hobbler, 'pause_process', mock.pause_process)
    monkeypatch.setattr(hobbler, 'restart_process', mock.restart_process)
    return mock

