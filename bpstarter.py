#!/usr/bin/python
#bpstarter.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
This is a Windows starter process.
It is used to check and update binaries before start up "bitpie.exe" process.

This file is a wrapper for `p2p.bpstarter <bitpie.p2p.bpstarter.html>`_ module.
See also `p2p.bptester <bitpie.p2p.bptester.html>`_ module.
"""

if __name__ == "__main__":
    import main.bpstarter
    main.bpstarter.run()


