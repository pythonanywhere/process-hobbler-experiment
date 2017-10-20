from unittest.mock import MagicMock, call
import asyncio
import os
import psutil
import pytest
import shutil
import subprocess
import tempfile
import time

import hobbler


@pytest.fixture
def fake_tarpit_dir():
    tempdir = tempfile.mkdtemp()
    open(os.path.join(tempdir, 'tasks'), 'w').close()
    yield tempdir
    shutil.rmtree(tempdir)


@pytest.fixture
def add_to_tarpit(pid, fake_tarpit_dir):
    with open(os.path.join(fake_tarpit_dir, 'tasks'), 'a') as f:
        f.write(str(pid) + '\n')


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

