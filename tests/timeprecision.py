
import sys
import time
# import timeit
# import platform


_InitTime = 0

def _time_windows():
    global _InitTime
    if _InitTime == 0:
        time.clock()
        _InitTime = time.time()
        print 'time init %10.10f' % _InitTime
    return _InitTime + time.clock()


if sys.platform == "win32":
    # On Windows, the best timer is time.clock()
    _time = _time_windows
else:
    # On most other platforms the best timer is time.time()
    _time = time.time

_time()

print '%f %f %f' % (time.time(), _time(), time.clock()) 

# for j in range(10):
# c = 0
for i in range(19999999):
    # c = i / float( i + 1 )
    if str(i).count('0') == 6:
        print '%f %f %f' % (time.time(), _time(), time.clock())


