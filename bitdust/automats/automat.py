#!/usr/bin/python
# automat.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

#------------------------------------------------------------------------------

from __future__ import absolute_import
import sys
import time
import traceback
from io import open

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.task import LoopingCall  #@UnresolvedImport
from twisted.internet.defer import Deferred, fail  #@UnresolvedImport

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

_LogFile = None  # : This is to have a separated Log file for state machines logs
_LogFilename = None
_LogsCount = 0  # : If not zero - it will print time since that value, not system time
_LogOutputHandler = None
_LogExceptionsHandler = None
_LifeBeginsTime = 0
_GlobalLogEvents = False
_GlobalLogTransitions = False

#------------------------------------------------------------------------------

_Counter = 0  # : Increment by one for every new object, the idea is to keep unique ID's in the index
_Index = {}  # : Index dictionary, unique id (string) to index (int)
_Objects = {}  # : Objects dictionary to store all state machines objects
_StateChangedCallback = None  # : Called when some state were changed

#------------------------------------------------------------------------------


def init():
    pass


def shutdown():
    global _Counter
    global _Index
    global _Objects
    global _StateChangedCallback
    LifeBegins(0)
    CloseLogFile()
    SetGlobalLogEvents()
    SetGlobalLogTransitions()
    SetExceptionsHandler(None)
    SetLogOutputHandler(None)
    _StateChangedCallback = None
    _Index.clear()
    _Objects.clear()
    _Counter = 0


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


def find(name):
    """
    Find state machine by name, this method will iterate all registered state machines
    and match "name" field to find the result.
    Return a list of indexes, then you can access those automats via `objects()` dict.
    """
    results = []
    for sm in objects().values():
        if sm.name == name:
            results.append(sm.index)
    return results


def by_index(index):
    """
    Returns state machine instance with given ``index`` if exists, otherwise returns `None`.
    """
    return objects().get(index, None)


def by_id(automat_id):
    """
    Returns state machine instance with given ``id`` if exists, otherwise returns `None`.
    """
    _index = index().get(automat_id, None)
    if _index is None:
        return None
    return by_index(_index)


def communicate(index, event, *args, **kwargs):
    """
    You can pass an event to any state machine - select by its ``index``.
    Use ``arg`` to pass extra data the conditions and actions methods.
    This method creates a Deferred object, pass it as a parameter with ``event``
    into the state machine and return that defer to outside - to catch result.
    In the action method you must call ``callback`` or ``errback`` to pass result.
    """
    A = by_index(index)
    if not A:
        return fail(Exception('state machine with index %d not exist' % index))
    d = Deferred()
    args = tuple(list(args) + [d])
    A.automat(event, *args, **kwargs)
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


def SetLogOutputHandler(cb):
    """
    Set callback to be fired when a log line is about to be printed from any state machine
    parameters are::

    cb(debug_level, message)
    """
    global _LogOutputHandler
    _LogOutputHandler = cb


def SetExceptionsHandler(cb):
    """
    Set callback to be fired when exception is caught from any state machine
    parameters are::

    cb(msg, exc_info)
    """
    global _LogExceptionsHandler
    _LogExceptionsHandler = cb


def RedirectLogFile(stream):
    """
    You can simple send all output to the stdout: import sys; RedirectLogFile(sys.stdout)
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
    if when is not None:
        _LifeBeginsTime = when
    else:
        _LifeBeginsTime = time.time()


def SetGlobalLogEvents(value=False):
    global _GlobalLogEvents
    _GlobalLogEvents = value


def SetGlobalLogTransitions(value=False):
    global _GlobalLogTransitions
    _GlobalLogTransitions = value


#------------------------------------------------------------------------------


class Automat(object):

    """
    Base class of the State Machine Object.

    You need to subclass this class and override the method ``A(event, *args, **kwargs)``.
    Constructor needs the ``name`` of the state machine and the
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

    fast = True
    """
    By default, incoming state machine events are passing via Twisted reactor like that:

        reactor.callLater(0, self.event, 'event-01', (arg1, arg2, ... ))

    But when ``fast = True`` event will be passed directly as function call of the state machine:

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

    def __init__(self, name, state, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=False, publish_event_state_not_changed=False, publish_fast=True, **kwargs):
        self.id, self.index = create_index(name)
        self.name = name
        self.state = state
        self.debug_level = debug_level
        self.log_events = log_events
        self.log_transitions = log_transitions
        self._timers = {}
        self._state_callbacks = {}
        self._callbacks_before_die = {}
        try:
            self.init(**kwargs)
        except Exception as exc:
            self.exc(msg='Exception in {}:{} automat init(), state is {}: {}'.format(self.id, self.name, self.state, exc))
            raise exc
        self.startTimers()
        self.register()
        self.publish_events = publish_events
        self.publish_event_state_not_changed = publish_event_state_not_changed
        self.publish_fast = publish_fast
        if _GlobalLogTransitions or self.log_transitions:
            self.log(self.debug_level, 'CREATED AUTOMAT with index %d, total running %d' % (self.index, len(objects())))

    def __del__(self):
        """
        Calls state changed callback and removes state machine from the index.
        """
        global _StateChangedCallback
        global _GlobalLogTransitions
        global _LogFile
        if self is None:
            self.log(self.debug_level, 'Some crazy stuff happens?')
            return
        automatid = self.id
        name = self.name
        index = self.index
        if _StateChangedCallback is not None:
            _StateChangedCallback(index, automatid, name, '')
        debug_level = self.debug_level or 0
        if erase_index:
            erase_index(automatid)
        if _GlobalLogTransitions or self.log_transitions:
            if _LogFile:
                self.log(debug_level, 'DESTROYED AUTOMAT with index %d, total running %d' % (index, len(objects())))

    def __repr__(self):
        """
        Will return something like: "network_connector(CONNECTED)".
        """
        return '%s(%s)' % (self.id, self.state)

    def A(self, event, *args, **kwargs):
        """
        Must define this method in subclass.

        This is the core method of the SWITCH-technology. I am using
        ``visio2python`` (created by me) to generate Python code from MS
        Visio drawing.
        """
        raise NotImplementedError

    def init(self, **kwargs):
        """
        Define this method in subclass to execute some code when creating a
        new instance of Automat class.
        """

    def shutdown(self):
        """
        Define this method in subclass to execute some code when closing an
        existing instance of Automat class.
        """

    def register(self):
        """
        Put reference to this automat instance into a global dictionary.
        """
        set_object(self.index, self)
        return self.index

    def unregister(self):
        """
        Removes reference to this instance from global dictionary tracking all state machines.
        """
        clear_object(self.index)
        return True

    def destroy(self, dead_state=None):
        """
        Call this method to remove the state machine from the ``objects()``
        dictionary and delete that instance.

        Be sure to not have any existing references on that instance so
        destructor will be called immediately.
        """
        self.shutdown()
        if dead_state:
            self.state = dead_state
        self._callbacks_before_die = self._state_callbacks.copy()
        self._state_callbacks.clear()
        self.stopTimers()
        return self.unregister()

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Redefine this method in subclass to be able to catch the moment
        immediately after automat's state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        Redefine this method in subclass if you want to do some actions
        immediately after processing the event, which did not change the
        automat's state.
        """

    def communicate(self, event_string, *args, **kwargs):
        """
        Use ``arg`` to pass extra data the conditions and actions methods. This
        method creates a Deferred object, pass it as a parameter with ``event``

        into the state machine and return that defer to outside - to catch result.
        In the action method you must call ``callback`` or ``errback`` to pass result.

        See ``addStateChangedCallback()`` for more advanced interactions/callbacks.
        """
        d = Deferred()
        if not args:
            args = tuple()
        args = tuple(list(args) + [d])
        self.automat(event_string, args)
        return d

    def automat(self, event, *args, **kwargs):
        """
        Call it like this::

            machineA.automat('init', arguments)

        to send some ``event`` to the State Machine Object.
        You can attach parameters to that event with ``arguments`` tuple.
        If ``self.fast=False`` - the ``self.A()`` method will be executed in delayed call.
        """
        _fast = kwargs.pop('fast', False)
        if self.fast or _fast:
            self.event(event, *args, **kwargs)
        else:
            delay = kwargs.pop('delay', 0)
            reactor.callLater(delay, self.event, event, *args, **kwargs)  # @UndefinedVariable
        return self

    def event(self, event, *args, **kwargs):
        """
        You can call ``event()`` directly to execute ``self.A()`` immediately,
        but preferred way is too call ``automat()`` method.

        Use ``fast = True`` flag to skip call to reactor.callLater(0, self.event, ...).
        """
        global _StateChangedCallback
        if _GlobalLogEvents or self.log_events:
            if self.log_events or not event.startswith('timer-'):
                self.log(self.debug_level, '%s fired with event "%s"' % (
                    repr(self),
                    event,
                ))
        old_state = self.state
        if self.post:
            try:
                new_state = self.A(event, *args, **kwargs)
            except Exception as exc:
                self.exc(msg='Exception in {}:{} automat, state is {}, event="{}" : {}'.format(self.id, self.name, self.state, event, exc))
                return self
            self.state = new_state
        else:
            try:
                self.A(event, *args, **kwargs)
            except Exception as exc:
                self.exc(msg='Exception in {}:{} automat, state is {}, event="{}" : {}'.format(self.id, self.name, self.state, event, exc))
                return self
            new_state = self.state
        if old_state != new_state:
            if _GlobalLogTransitions or self.log_transitions:
                self.log(self.debug_level, '%s(%s): (%s)->(%s)' % (
                    repr(self),
                    event,
                    old_state,
                    new_state,
                ))
            self.stopTimers()
            self.state_changed(old_state, new_state, event, *args, **kwargs)
            if self.publish_events:
                self.pushEvent(old_state, new_state, event)
            self.startTimers()
            if _StateChangedCallback is not None:
                _StateChangedCallback(self.index, self.id, self.name, new_state)
        else:
            self.state_not_changed(self.state, event, *args, **kwargs)
            if self.publish_events:
                if self.publish_event_state_not_changed:
                    self.pushEvent(old_state, new_state, event)
        self.executeStateChangedCallbacks(old_state, new_state, event, *args, **kwargs)
        return self

    def timerEvent(self, name, interval):
        """
        This method fires the timer events.
        """
        try:
            if name in self.timers and self.state in self.timers[name][1]:
                self.automat(name)
            else:
                if _GlobalLogEvents or self.log_events:
                    self.log(self.debug_level, '%s.timerEvent ERROR timer %s not found in self.timers' % (str(self), name))
        except:
            self.exc()

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

    def to_json(self, short=True):
        if short:
            return {
                'index': self.index,
                'id': self.id,
                'name': self.__class__.__name__,
                'state': self.state,
            }
        return {
            'index': self.index,
            'id': self.id,
            'name': self.__class__.__name__,
            'state': self.state,
            'repr': repr(self),
            'timers': (','.join(list(self.getTimers().keys()))),
            'events': self.publish_events,
        }

    def exc(self, msg='', to_logfile=False, exc_type=None, exc_value=None, exc_traceback=None):
        """
        Print exception in stdout, optionally to log file.
        """
        global _LogExceptionsHandler
        global _LogFile
        _t = exc_type
        _v = exc_value
        _tb = exc_traceback
        if exc_type is None or exc_value is None or exc_traceback is None:
            _t, _v, _tb = sys.exc_info()
        exc_type = _t if exc_type is None else exc_type
        exc_value = _v if exc_value is None else exc_value
        exc_traceback = _tb if exc_traceback is None else exc_traceback
        e = ''
        if exc_value is not None or exc_traceback is not None:
            e = traceback.format_exception(exc_type, value=exc_value, tb=exc_traceback)
        else:
            e = traceback.format_exc()
        if to_logfile and _LogFile is not None:
            if msg:
                self.log(0, msg)
            self.log(0, e)
        if _LogExceptionsHandler is not None:
            _LogExceptionsHandler(msg=msg, exc_info=(
                exc_type,
                exc_value,
                exc_traceback,
            ))

    def log(self, level, text):
        """
        Print log message.

        See ``OpenLogFile()`` and ``CloseLogFile()`` methods.
        """
        global _LogFile
        global _LogFilename
        global _LogsCount
        global _LifeBeginsTime
        global _LogOutputHandler
        if not text.startswith(self.name):
            text = '%s(): %s' % (
                self.name,
                text,
            )
        if _LogOutputHandler is not None:
            _LogOutputHandler(level, text)
        else:
            if _LogFile is not None:
                if _LogsCount > 100000 and _LogFilename:
                    # very simple log rotation
                    _LogFile.close()
                    _LogFile = open(_LogFilename, 'w')
                    _LogsCount = 0
                s = ' '*level + text + '\n'
                tm_str = time.strftime('%H:%M:%S')
                if _LifeBeginsTime != 0:
                    dt = time.time() - _LifeBeginsTime
                    mn = dt // 60
                    sc = dt - mn*60
                    tm_str += ('/%02d:%02d.%02d' % (mn, sc, (sc - int(sc))*100))
                s = tm_str + s
                if sys.version_info[0] == 3:
                    if not isinstance(s, str):
                        s = s.decode('utf-8')
                else:
                    if not isinstance(s, unicode):  # @UndefinedVariable
                        s = s.decode('utf-8')
                try:
                    _LogFile.write(s)
                    _LogFile.flush()
                except:
                    pass
                _LogsCount += 1

    def addStateChangedCallback(self, cb, oldstate=None, newstate=None, callback_id=None):
        """
        You can add a callback function to be executed when state machine
        reaches particular condition, it will be called with such arguments:

            cb(oldstate, newstate, event_string, *args, **kwargs)

        For example, method_B() will be called when machine_A become "ONLINE":

            machine_A.addStateChangedCallback(method_B, None, "ONLINE")

        If you set "None" to both arguments,
        the callback will be executed every time when the state gets changed:

            machineB.addStateChangedCallback(method_B)

        """
        key = (
            oldstate,
            newstate,
        )
        if key not in self._state_callbacks:
            self._state_callbacks[key] = []
        if cb not in self._state_callbacks[key]:
            self._state_callbacks[key].append((callback_id, cb))
        return True

    def removeStateChangedCallback(self, cb=None, callback_id=None):
        """
        Remove given callback from the state machine.
        """
        removed_count = 0
        for key in list(self._state_callbacks.keys()):
            cb_list = self._state_callbacks[key]
            for cb_tupl in cb_list:
                cb_id_, cb_ = cb_tupl
                if cb and cb == cb_:
                    self._state_callbacks[key].remove(cb_tupl)
                    removed_count += 1
                if callback_id and callback_id == cb_id_:
                    self._state_callbacks[key].remove(cb_tupl)
                    removed_count += 1
                if len(self._state_callbacks[key]) == 0:
                    self._state_callbacks.pop(key)
        return removed_count

    def removeStateChangedCallbackByState(self, oldstate=None, newstate=None):
        """
        Removes all callback methods with given condition.

        This is useful if you use ``lambda x: do_somethig()`` to catch
        the moment when state gets changed.
        """
        for key in list(self._state_callbacks.keys()):
            if key == (
                oldstate,
                newstate,
            ):
                self._state_callbacks.pop(key)
                break

    def executeStateChangedCallbacks(self, oldstate, newstate, event_string, *args, **kwargs):
        """
        Compare conditions and execute state changed callback methods.
        """
        for key, cb_list in list(self._state_callbacks.items()) + list(self._callbacks_before_die.items()):
            old, new = key
            catched = False
            if old is None and new is None:
                catched = True
            elif old is None and new == newstate and newstate != oldstate:
                catched = True
            elif new is None and old == oldstate and newstate != oldstate:
                catched = True
            elif old == oldstate and new == newstate:
                catched = True
            if catched:
                for cb_tupl in cb_list:
                    _, cb = cb_tupl
                    cb(oldstate, newstate, event_string, *args, **kwargs)
        self._callbacks_before_die.clear()

    def publishEvents(self, on_off, publish_event_state_not_changed=None, publish_fast=None):
        """
        This can be used to enable "publishing" of all updates of the state machine to external "listeners".
        """
        self.publish_events = bool(on_off)
        if publish_event_state_not_changed is not None:
            self.publish_event_state_not_changed = publish_event_state_not_changed
        if publish_fast is not None:
            self.publish_fast = publish_fast

    def pushEvent(self, oldstate, newstate, event_string, publisher=None):
        """
        Can be used to
        """
        state_snapshot = dict(
            index=self.index,
            id=self.id,
            name=self.__class__.__name__,
            newstate=newstate,
            oldstate=oldstate,
            event=event_string,
        )
        if publisher is not None:
            if self.publish_fast:
                publisher(state_snapshot)
            else:
                reactor.callLater(0, publisher, state_snapshot)  # @UndefinedVariable
            return
        from bitdust.main import events
        events.send('state-changed', data=state_snapshot, fast=self.publish_fast)
