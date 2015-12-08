An experimental "process hobbler" that starts and stops processes.  Was
interesting for learning asyncio, but also for comparing asyncio vs other
python multitasking solutions -- I tried gevent and threads.

None of them performed well enough to make it a viable tool, since the
hobbler would take up more CPU hobbling processes than seemed likely
to have been saved from having those processes hobbled.  (Warning: no science
here!)


# Running the tests

Use the requirements file to create a virtualenv.  Tested with Python3.4 and 3.5.

    py.test  # runs all tests
    py.test -s # prints more stuff to stdout, useful for debugging
    py.test -k lots # runs the main performance test

# Comparing asyncio with other solutions

    git fetch --tags
    git checkout gevent
    py.test -s -k lots
    git checkout threads
    py.test -s -k lots

