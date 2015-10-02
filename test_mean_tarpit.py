import pytest
import threading


from mean_tarpit import main

@pytest.fixture
def start_main_in_thread():
    thread = threading.Thread(target=lambda: main('/tmp/fake-tarpit'))
    thread.start()

def test_tarpit_process_is_slow(start_main_in_thread):
    pass

