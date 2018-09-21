"""
science.py: Module containing functions to log performance for later statistical
analysis.

This is different than the normal logging module because we always want to save
science information, but it's not really a log level like ERROR or WARNING. We
also want the science information to be machine-parseable.

Science information is logged as a TSV with 4 columns:

    - Hostname
    - Time
    - Event
    - Value (optional)

Additionally, we support auto-magic named timers with statr_timer and end_timer,
where the elapsed times are automatically logged.

We can also log the sizes of files and, if on Unix, current process memory
usage.

"""

from __future__ import absolute_import
import sys
import socket
import time
import threading
import os
from io import open

try:
    import resource
except BaseException:    # We couldn't import the resource module; we are probably not running on
    # Unix. Memory logging will be a no-op.

    # Remember that the module is unavailable.
    resource = None

# This holds the science logging output stream that the module uses.
log_stream = None

# This holds the time format to use
time_format = "%Y-%m-%d  %H:%M:%S"

# This holds a dict of active timer start times by name.
timers = {}

# This holds our global module lock
lock = threading.RLock()


def log_to(log_filename):
    """
    Set up science logging to a file with the given name.

    """

    with lock:

        # We need to replace the module-level variable
        global log_stream

        # Open up the new log stream
        log_stream = open(log_filename, "a")


def log_event(event, value=None):
    """
    Log the given event.

    """

    with lock:

        # What time is it right now?
        now = time.gmtime()

        # This holds all the parts we are going to assemble
        parts = [socket.getfqdn(), time.strftime(time_format, now), str(event)]

        if value is not None:
            # We got a value and should log that too.
            parts.append(str(value))

        if log_stream is not None:
            # Log to the science output stream.
            log_stream.write("\t".join(parts))
            log_stream.write("\n")
            log_stream.flush()


def start_timer(name, replace=True):
    """
    Start a named timer with the given name. If replace is false, don't change
    the start time if it already exists.

    """

    # Record the time we were called at
    start_time = time.clock()

    with lock:

        if replace or name not in timers:
            # Start the timer by saving the current clock value (which is a
            # float in seconds, but is supposed to be good to the microsecond or
            # thereabouts.
            timers[name] = start_time


def stop_timer(name):
    """
    Stop a named timer and log the elapsed time in seconds, under the timer
    name. Does nothing if the timer is not started.

    """

    # Record the time we were called at
    stop_time = time.clock()

    with lock:

        if name in timers:
            # How long elapsed?
            elapsed_time = stop_time - timers[name]

            # Log the time
            log_event(name, elapsed_time)

            # Cancel the timer
            del timers[name]


def log_filesize(name, filename):
    """
    Log an event with the given name, and a value equal to the current size of
    the file with the given file name, in bytes.

    Nonexistent files have size 0.

    """

    try:
        # What is the file size?
        size = os.path.getsize(filename)
    except os.error:
        # File probably doesn't exist.
        size = 0

    # Log the size event.
    log_event(name, size)


def log_memory():
    """
    Logs the current memory usage of the process, if available.

    Memory usage is in whatever unit the resource module uses, probably
    kilobytes, and is logged as "memory_usage".

    """

    if resource is None:
        # Can't log memory without the resource module.
        return

    try:
        # Get the memory usage. See <http://stackoverflow.com/a/7669482/402891>.
        # Apparently "memory usage" is best described as "max resident set
        # size".
        memory_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        log_event("memory_usage", memory_usage)
    except resource.error:
        # Skip errors due to resource not working properly.
        pass
