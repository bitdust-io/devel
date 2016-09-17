#!/usr/bin/python
#events.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (events.py) is part of BitDust Software.
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
.. module:: events

A very simple "event" system, just to show and remember what is going on.
TODO:
need to store events on the local HDD
"""

import os
import sys
import time

#------------------------------------------------------------------------------ 

_OutputFunc = None

#------------------------------------------------------------------------------ 

def init(output_func):
    global _OutputFunc
    _OutputFunc = output_func


def call(typ, module, message, text=''):
    global _OutputFunc
    if _OutputFunc is None:
        return
    _OutputFunc('event %s (((%s))) [[[%s]]] %s' % (typ, module, message, text))

def info(module, message, text=''):
    call('info', module, message, text)
    

def notify(module, message, text=''):
    call('notify', module, message, text)


def warning(module, message, text=''):
    call('warning', module, message, text)

    
   
