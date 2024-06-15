#!/usr/bin/python
# __init__.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (__init__.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
#
#
#
#
"""
`BitDust <https://bitdust.io>`_ is a peer to peer online backup utility.

This is a distributed network for backup data storage.
Each participant of the network provides a portion of his hard drive for other users.
In exchange, he is able to store his data on other peers.

The redundancy in backup makes it so if someone loses your data,
you can rebuild what was lost and give it to someone else to hold.
And all of this happens without you having to do a thing - the software keeps your data in safe.

All your data is encrypted before it leaves your computer with a Private key your computer generates.
No one else can read your data, even BitDust !
Recover data is only one way - download the necessary pieces from computers of other peers
and decrypt them with your private key.

`BitDust <https://bitdust.io>`_ is written in `Python <http://python.org/>`_
using pure `Twisted framework <http://twistedmatrix.com/>`_.
"""
