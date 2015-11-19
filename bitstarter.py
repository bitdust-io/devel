#!/usr/bin/python
#bitstarter.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
This is a Windows starter process.
It is used to check and update binaries before start up "bitdust.exe" process.

This file is a wrapper for `p2p.bitstarter <bitdust.p2p.bitstarter.html>`_ module.
See also `p2p.bptester <bitdust.p2p.bptester.html>`_ module.
"""

if __name__ == "__main__":
    import main.bitstarter
    main.bitstarter.run()


