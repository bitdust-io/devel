#!/usr/bin/env python
# ppworker.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (ppworker.py) is part of BitDust Software.
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
# Parallel Python Software: http://www.parallelpython.com
# Copyright (c) 2005-2009, Vitalii Vanovschi
# All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the author nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
"""
Parallel Python Software, PP Worker.

http://www.parallelpython.com - updates, documentation, examples and support
forums
"""
from __future__ import absolute_import
from __future__ import print_function
import sys
import os
import StringIO
import six.moves.cPickle as pickle
from . import pptransport

try:
    import msvcrt
    msvcrt.setmode(1, os.O_BINARY)
    msvcrt.setmode(2, os.O_BINARY)
except:
    pass

copyright = "Copyright (c) 2005-2009 Vitalii Vanovschi. All rights reserved"
version = "1.5.7"


def import_module(name):
    mod = __import__(name)
    components = name.split('.')
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


def preprocess(msg):
    fname, fsources, imports = pickle.loads(msg)
    fobjs = [compile(fsource, '<string>', 'exec') for fsource in fsources]
    for module in imports:
        try:
            globals()[module.split('.')[0]] = __import__(module)
        except:
            print("An error has occured during the module import")
            sys.excepthook(*sys.exc_info())
    return fname, fobjs


class _WorkerProcess(object):

    def __init__(self):
        self.hashmap = {}
        self.e = sys.__stderr__
        self.sout = StringIO()
#        self.sout = open("/tmp/pp.debug","a+")
        origsout = sys.stdout
        sys.stdout = self.sout
        sys.stderr = self.sout
        self.t = pptransport.CPipeTransport(sys.stdin, origsout)  # sys.__stdout__)
        self.t.send(str(os.getpid()))
        self.pickle_proto = int(self.t.receive())

    def run(self):
        try:
            # execution cycle
            while True:

                __fname, __fobjs = self.t.creceive(preprocess)

                __sargs = self.t.receive()

                for __fobj in __fobjs:
                    try:
                        eval(__fobj)
                        globals().update(locals())
                    except:
                        print("An error has occured during the " + \
                              "function import")
                        sys.excepthook(*sys.exc_info())

                __args = pickle.loads(__sargs)

                __f = locals()[__fname]
                try:
                    __result = __f(*__args)
                except:
                    print("An error has occured during the function execution")
                    sys.excepthook(*sys.exc_info())
                    __result = None

                __sresult = pickle.dumps((__result, self.sout.getvalue()),
                                         self.pickle_proto)
                self.t.send(__sresult)
                self.sout.truncate(0)
        except:
            print("Fatal error has occured during the function execution")
            sys.excepthook(*sys.exc_info())
            __result = None
            __sresult = pickle.dumps((__result, self.sout.getvalue()),
                                     self.pickle_proto)
            self.t.send(__sresult)


if __name__ == "__main__":
    sys.path.append(os.path.dirname(__file__))
    wp = _WorkerProcess()
    wp.run()

# Parallel Python Software: http://www.parallelpython.com
