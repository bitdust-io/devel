
import time
import timeit
time.clock()
time.sleep(1)
print (time.time(), time.clock(), timeit.default_timer())
time.sleep(1)
print (time.time(), time.clock(), timeit.default_timer())