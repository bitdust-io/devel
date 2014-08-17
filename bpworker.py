#!/usr/bin/python
#bpworker.py
#
# <<<COPYRIGHT>>>
#
#
#
#

if __name__ == "__main__":
    import os
    import sys
    sys.path.append(os.path.abspath(os.path.join('.', 'parallelp', 'pp')))
    from parallelp.pp.ppworker import _WorkerProcess
    wp = _WorkerProcess()
    wp.run() 

 