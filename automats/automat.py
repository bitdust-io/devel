#!/usr/bin/python
# automat.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (automat.py) is part of BitDust Software.
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
.. module:: automat.

This is the base class for State Machine.
The BitDust project is developing in principles of
`Automata-based programming <http://en.wikipedia.org/wiki/Automata-based_programming>`_.

This is a programming paradigm in which the program or its part is thought of as a model of a
`finite state machine <http://en.wikipedia.org/wiki/Finite_state_machine>`_ or any other formal automaton.

Its defining characteristic is the use of finite state machines to
`describe program behavior <http://en.wikipedia.org/wiki/State_diagram>`_.

The transition graphs of state machines are used in all stages of software development:
- specification,
- implementation,
- debugging and
- documentation.

You can see Transition graph for all BitDust state machines in the file
`automats.pdf <https://bitdust.io/automats.pdf>`_,
MS Visio, 'editable' version:
`automats.vsd <https://bitdust.io/automats.vsd>`_,
stencils is here: `automats.vss <https://bitdust.io/automats.vss>`_

A small tool called `visio2python <http://code.google.com/p/visio2python/>`_
was written to simplify working with the BitDust project.

It can translate transition graphs created in Microsoft Visio into Python code.

Automata-Based Programming technology was introduced by Anatoly Shalyto in 1991 and Switch-technology was
developed to support automata-based programming.
Automata-Based Programming is considered to be rather general purpose program development methodology
than just another one finite state machine implementation.
Anatoly Shalyto is the former of
`Foundation for Open Project Documentation <http://en.wikipedia.org/wiki/Foundation_for_Open_Project_Documentation>`_.

Read more about Switch-technology on the Saint-Petersburg National Research University
of Information Technologies, Mechanics and Optics, Programming Technologies Department
`Page <http://is.ifmo.ru/english>`_.
"""

import sys
import time
import traceback

from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.internet.defer import Deferred, fail
from twisted.python.failure import Failure

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 12
_LogEvents = True

#------------------------------------------------------------------------------

_Counter = 0  # : Increment by one for every new object, the idea is to keep unique ID's in the index
_Index = {}  # : Index dictionary, unique id (string) to index (int)
_Objects = {}  # : Objects dictionary to store all state machines objects
_StateChangedCallback = None  # : Called when some state were changed
_LogFile = None  # : This is to have a separated Log file for state machines logs
_LogFilename = None
_LogsCount = 0  # : If not zero - it will print time since that value, not system time
_LifeBeginsTime = 0

#------------------------------------------------------------------------------


def get_new_index():
    """
    Just get the current index and increase by one.
    """
    global _Counter
    _Counter += 1
    return _Counter


def create_index(name):
    """
    Generate unique ID, and put it into Index dict, increment counter.
    """
    global _Index
    automatid = name
    if id in _Index:
        i = 1
        while automatid + '(' + str(i) + ')' in _Index:
            i += 1
        automatid = name + '(' + str(i) + ')'
    _Index[automatid] = get_new_index()
    return automatid, _Index[automatid]


def erase_index(automatid):
    """
    Removes given unique automat ID from Index dict and returns its index number or None if ID was not found.
    """
    global _Index
    if _Index is None:
        return None
    return _Index.pop(automatid, None)
#     index = _Index.get(automatid, None)
#     if index is None:
#         return None
#     del _Index[automatid]


def set_object(index, obj):
    """
    Put object for that index into memory.
    """
    global _Objects
    _Objects[index] = obj


def clear_object(index):
    """
    Clear object with given index from memory.
    """
    global _Objects
    if _Objects is None:
        return
    return _Objects.pop(index, None)
#     if index in _Objects:
#         del _Objects[index]


def objects():
    """
    Get all state machines stored in memory.
    """
    global _Objects
    return _Objects


def index():
    """
    Get all indexed state machines - should match with objects()
    """
    global _Index
    return _Index


def communicate(index, event, arg=None):
    """
    You can pass an event to any state machine - select by its ``index``.
    Use ``arg`` to pass extra data the conditions and actions methods.
    This method creates a Deferred object, pass it as a parameter with ``event``
    into the state machine and return that defer to outside - to catch result.
    In the action method you must call ``callback`` or ``errback`` to pass result.
    """
    A = objects().get(index, None)
    if not A:
        return fail(Failure(Exception('state machine with index %d not exist' % index)))
    d = Deferred()
    args = (d, arg)
    A.automat(event, args)
    return d

#------------------------------------------------------------------------------


def SetStateChangedCallback(cb):
    """
    Set callback to be fired when any state machine changes its state Callback
    parameters are::

    cb(index, id, name, new state)
    """
    global _StateChangedCallback
    _StateChangedCallback = cb


def RedirectLogFile(stream):
    """
    You can simple send all output to the stdout:

    import sys RedirectLogFile(sys.stdout)
    """
    global _LogFile
    _LogFile = stream


def OpenLogFile(filename):
    """
    Open a file to write logs from all state machines.

    Very useful during debug.
    """
    global _LogFile
    global _LogFilename
    if _LogFile:
        return
    _LogFilename = filename
    try:
        _LogFile = open(_LogFilename, 'w')
    except:
        _LogFile = None


def CloseLogFile():
    """
    Close the current log file, you can than open it again.
    """
    global _LogFile
    if not _LogFile:
        return
    _LogFile.flush()
    _LogFile.close()
    _LogFile = None
    _LogFilename = None


def LifeBegins(when=None):
    """
    Call that function during program start up to print relative time in the
    logs, not absolute.
    """
    global _LifeBeginsTime
    if when:
        _LifeBeginsTime = when
    else:
        _LifeBeginsTime = time.time()

#------------------------------------------------------------------------------


class Automat(object):
    """
    Base class of the State Machine Object.

    You need to subclass this class and override the method ``A(event,
    arg)``. Constructor needs the ``name`` of the state machine and the
    beginning ``state``. At first it generate an unique ``id`` and new
    ``index`` value. You can use ``init()`` method in the subclass to
    call some code at start. Finally put the new object into the memory
    with given index - it is placed into ``objects()`` dictionary. To
    remove the instance call ``destroy()`` method.
    """

    state = 'NOT_EXIST'
    """
    This is a string representing current Machine state, must be set in the constructor.
    ``NOT_EXIST`` indicates that this machine is not created yet.
    A blank state is a fundamental mistake!
    """

    timers = {}
    """
    A dictionary of timer events fired at specified intervals when machine rich given state:
          timers = {'timer-60sec':     (60,     ['STATE_A',]),
                    'timer-3min':      (60*3,   ['STATE_B', 'STATE_C',]), }
    """

    instant_timers = False
    """
    Set this to True and timers will not skip first iteration.
    See method self.startTimers().
    """

    fast = False
    """
    By default, a state machine is called like this::

        reactor.callLater(0, self.event, 'event-01', (arg1, arg2, ... ))

    If ``fast = True`` it will call state machine method directly:

        self.event('event-01', (arg1, arg2, ... ))

    """

    post = False
    """
    Sometimes need to set the new state AFTER finish all actions.
    Set ``post = True`` to call ``self.state = <newstate>``
    in the ``self.event()`` method, but not in the ``self.A()`` method.
    You also must set that flag in the MS Visio document and rebuild the code:
    put ``[post]`` string into the last line of the LABEL shape.
    """

    def __init__(self, name, state, debug_level=_DebugLevel * 2, log_events=False):
        self.id, self.index = create_index(name)
        self.name = name
        self.state = state
        self.debug_level = debug_level
        self.log_events = log_events
        self.log_transitions = log_events
        self._timers = {}
        self._state_callbacks = {}
        self.init()
        self.startTimers()
        self.register()
        if _Debug:
            self.log(max(_DebugLevel, self.debug_level),
                     'CREATED AUTOMAT %s with index %d, %d running' % (
                str(self), self.index, len(objects())))

    def register(self):
        """
        Put reference to this automat instance into a global dictionary.
        """
        set_object(self.index, self)

    def unregister(self):
        """
        Removes reference to this instance from global dictionary tracking all state machines.
        """
        clear_object(self.index)

    def __del__(self):
        """
        Calls state changed callback and removes state machine from the index.
        """
        global _StateChangedCallback
        if self is None:
            # Some crazy stuff happens? :-)
            return
        o = self
        automatid = self.id
        name = self.name
        index = self.index
        if _StateChangedCallback is not None:
            _StateChangedCallback(index, automatid, name, '')
        debug_level = max(_DebugLevel, self.debug_level)
        erase_index(automatid)
        if _Debug:
            self.log(debug_level,
                     'DESTROYED AUTOMAT %s with index %d, %d running' % (
                         str(o), index, len(objects())))

    def __repr__(self):
        """
        Will print something like: "network_connector(CONNECTED)".
        """
        return '%s(%s)' % (self.id, self.state)

    def A(self, event, arg):
        """
        Must define this method in subclass.

        This is the core method of the SWITCH-technology. I am using
        ``visio2python`` (created by me) to generate Python code from MS
        Visio drawing.
        """
        raise NotImplementedError

    def init(self):
        """
        Define this method in subclass to execute some code when creating an
        object.
        """

    def destroy(self, dead_state='NOT_EXIST'):
        """
        Call this method to remove the state machine from the ``objects()``
        dictionary and delete that instance.

        Be sure to not have any existing references on that instance so
        destructor will be called immediately.
        """
        self._state_callbacks.clear()
        self.stopTimers()
        self.state = dead_state
        objects().pop(self.index)

    def state_changed(self, oldstate, newstate, event_string, arg):
        """
        Redefine this method in subclass to be able to catch the moment
        immediately after automat's state were changed.
        """

    def state_not_changed(self, curstate, event_string, arg):
        """
        Redefine this method in subclass if you want to do some actions
        immediately after processing the event, which did not change the
        automat's state.
        """

    def communicate(self, event_string, arg=None):
        """
        Use ``arg`` to pass extra data the conditions and actions methods. This
        method creates a Deferred object, pass it as a parameter with ``event``

        into the state machine and return that defer to outside - to catch result.
        In the action method you must call ``callback`` or ``errback`` to pass result.

        See ``addStateChangedCallback()`` for more advanced interactions/callbacks.
        """
        d = Deferred()
        args = arg
        if not args:
            args = ()
        args = tuple(list(args) + [d, ])
        self.automat(event_string, args)
        return d

    def automat(self, event_string, arg=None):
        """
        Call it like this::

            machineA.automat('init', arguments)

        to send some ``event`` to the State Machine Object.
        You can attach parameters to that event with ``arguments`` tuple.
        If ``self.fast=False`` - the ``self.A()`` method will be executed in delayed call.
        """
        if self.fast:
            self.event(event_string, arg)
        else:
            reactor.callLater(0, self.event, event_string, arg)  # @UndefinedVariable

    def event(self, event_string, arg=None):
        """
        You can call ``event()`` directly to execute ``self.A()`` immediately,
        but preferred way is too call ``automat()`` method.

        Use ``fast = True`` flag to skip call to reactor.callLater(0, self.event, ...).
        """
        global _StateChangedCallback
        if _LogEvents and self.log_events and _Debug:
            if self.log_events or not event_string.startswith('timer-'):
                self.log(
                    max(self.debug_level, _DebugLevel),
                    '%s fired with event "%s", refs=%d' % (
                        repr(self), event_string, sys.getrefcount(self)))
        old_state = self.state
        if self.post:
            try:
                new_state = self.A(event_string, arg)
            except:
                if _Debug:
                    self.exc('Exception in {}:{} automat, state is {}, event="{}", arg={}'.format(
                        self.id, self.name, self.state, event_string, arg))
            self.state = new_state
        else:
            try:
                self.A(event_string, arg)
            except:
                if _Debug:
                    self.exc('Exception in {}:{} automat, state is {}, event="{}", arg={}'.format(
                        self.id, self.name, self.state, event_string, arg))
            new_state = self.state
        if old_state != new_state:
            if _Debug and self.log_transitions:
                self.log(
                    max(_DebugLevel, self.debug_level),
                    '%s(%s): (%s)->(%s)' % (
                        repr(self), event_string, old_state, new_state))
            self.stopTimers()
            self.state_changed(old_state, new_state, event_string, arg)
            self.startTimers()
            if _StateChangedCallback is not None:
                _StateChangedCallback(self.index, self.id, self.name, new_state)
        else:
            self.state_not_changed(self.state, event_string, arg)
        self.executeStateChangedCallbacks(old_state, new_state, event_string, arg)

    def timerEvent(self, name, interval):
        """
        This method fires the timer events.
        """
        if name in self.timers and self.state in self.timers[name][1]:
            self.automat(name)
        else:
            self.log(
                max(_DebugLevel, self.debug_level),
                '%s.timerEvent ERROR timer %s not found in self.timers' % (str(self), name))

    def stopTimers(self):
        """
        Stop all state machine timers.
        """
        for name, timer in self._timers.items():  # @UnusedVariable
            if timer.running:
                timer.stop()
        self._timers.clear()

    def startTimers(self):
        """
        Start all state machine timers.
        """
        for name, (interval, states) in self.timers.items():
            if len(states) > 0 and self.state not in states:
                continue
            self._timers[name] = LoopingCall(self.timerEvent, name, interval)
            self._timers[name].start(interval, self.instant_timers)
            # self.log(self.debug_level * 4, '%s.startTimers timer %s started' % (self, name))

    def restartTimers(self):
        """
        Restart all state machine timers.

        When state is changed - all internal timers is restarted.
        You can use external timers if you do not need that, call::

            machineA.automat('timer-1sec')

        to fire timer event from outside.
        """
        self.stopTimers()
        self.startTimers()

    def getTimers(self):
        """
        Get internal timers dictionary.
        """
        return self._timers

    def exc(self, msg='', to_logfile=False):
        """
        Print exception in stdout, optionally to log file.
        """
        global _LogFile
        e = traceback.format_exc()
        if to_logfile and _LogFile is not None:
            if msg:
                self.log(0, msg)
            self.log(0, e)
        try:
            from logs import lg
            lg.exc(msg)
        except:
            pass

    def log(self, level, text):
        """
        Print log message.

        See ``OpenLogFile()`` and ``CloseLogFile()`` methods.
        """
        global _LogFile
        global _LogFilename
        global _LogsCount
        global _LifeBeginsTime
        if _LogFile is not None:
            if _LogsCount > 100000 and _LogFilename:
                _LogFile.close()
                _LogFile = open(_LogFilename, 'w')
                _LogsCount = 0

            s = ' ' * level + text + '\n'
            if _LifeBeginsTime != 0:
                dt = time.time() - _LifeBeginsTime
                mn = dt // 60
                sc = dt - mn * 60
                s = ('%02d:%02d.%02d' % (mn, sc, (sc - int(sc)) * 100)) + s
            else:
                s = time.strftime('%H:%M:%S') + s

            _LogFile.write(s)
            _LogFile.flush()
            _LogsCount += 1
        else:
            try:
                from logs import lg
                lg.out(level, text)
            except:
                pass

    def addStateChangedCallback(self, cb, oldstate=None, newstate=None):
        """
        You can add a callback function to be executed when state machine
        reaches particular condition, it will be called with such arguments:

            cb(oldstate, newstate, event_string, args)

        For example, method_B() will be called when machine_A become "ONLINE":

            machine_A.addStateChangedCallback(method_B, None, "ONLINE")

        If you set "None" to both arguments,
        the callback will be executed every time when the state gets changed:

            machineB.addStateChangedCallback(method_B)

        """
        key = (oldstate, newstate)
        if key not in self._state_callbacks:
            self._state_callbacks[key] = []
        if cb not in self._state_callbacks[key]:
            self._state_callbacks[key].append(cb)

    def removeStateChangedCallback(self, cb):
        """
        Remove given callback from the state machine.
        """
        for key, cb_list in self._state_callbacks.items():
            for cb_ in cb_list:
                if cb == cb_:
                    self._state_callbacks[key].remove(cb)
                    if len(self._state_callbacks[key]) == 0:
                        self._state_callbacks.pop(key)

    def removeStateChangedCallbackByState(self, oldstate=None, newstate=None):
        """
        Removes all callback methods with given condition.

        This is useful if you use ``lambda x: do_somethig()`` to catch
        the moment when state gets changed.
        """
        for key in self._state_callbacks.keys():
            if key == (oldstate, newstate):
                self._state_callbacks.pop(key)
                break

    def executeStateChangedCallbacks(self, oldstate, newstate, event_string, args):
        """
        Compare conditions and execute state changed callback methods.
        """
        for key, cb_list in self._state_callbacks.items():
            old, new = key
            catched = False
            if old is None and new is None:
                catched = True
            elif old is None and new == newstate:
                catched = True
            elif new is None and old == oldstate:
                catched = True
            elif old == oldstate and new == newstate:
                catched = True
            if catched:
                for cb in cb_list:
                    cb(oldstate, newstate, event_string, args)
