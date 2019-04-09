#!/usr/bin/python
# raidutils.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (raidutils.py) is part of BitDust Software.
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
.. module:: raidutils.

"""

import array


def build_parity(sds, iters, datasegments, myeccmap, paritysegments):
    psds_list = {seg_num: array.array('i') for seg_num in range(myeccmap.paritysegments)}

    for i in range(iters):
        parities = {seg_num: 0 for seg_num in range(myeccmap.paritysegments)}
        for DSegNum in range(datasegments):
            b = next(sds[DSegNum])

            Map = myeccmap.DataToParity[DSegNum]
            for PSegNum in Map:
                if PSegNum > paritysegments:
                    myeccmap.check()
                    raise Exception("eccmap error")

                parities[PSegNum] = parities[PSegNum] ^ b

        for PSegNum in range(myeccmap.paritysegments):
            psds_list[PSegNum].append(parities[PSegNum])

    for PSegNum in psds_list:
        psds_list[PSegNum].byteswap()

    return psds_list


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]
