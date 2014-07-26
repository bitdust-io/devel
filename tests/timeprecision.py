
import os
import sys
import time
# import timeit
# import platform


def _qpc():
    from ctypes import byref, c_int64, windll
    val = c_int64()
    windll.Kernel32.QueryPerformanceCounter(byref(val))
    return val.value    


_InitTime = None
_TimeStart = None
_Frequency = None


def init():
    global _InitTime
    global _TimeStart
    global _Frequency
    _InitTime = time.time()
    # time.clock()
    from ctypes import byref, c_int64, windll
    time_start = c_int64()
    freq = c_int64()
    windll.Kernel32.QueryPerformanceCounter(byref(time_start))
    windll.Kernel32.QueryPerformanceFrequency(byref(freq))
    _TimeStart = float(time_start.value)
    _Frequency = float(freq.value)


def _time_windows():
    global _InitTime
    global _TimeStart
    global _Frequency
    from ctypes import byref, c_int64, windll
    time_now = c_int64()
    windll.Kernel32.QueryPerformanceCounter(byref(time_now))
    return _InitTime + ( (_TimeStart - time_now.value) / _Frequency)


if sys.platform == "win32":
    # On Windows, the best timer is time.clock()
    _time = _time_windows
    init()
else:
    # On most other platforms the best timer is time.time()
    _time = time.time

print '%f' % (time.time() - _time()) 

for j in range(10):
    c = 0
    for i in range(9999999):
        c = i / float( i + 1 )
        if str(i).count('0') == 6 and int(str(i)[0]) % 5:
            print '%f' % (time.time() - _time())


