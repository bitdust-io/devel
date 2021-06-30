#!/usr/bin/env python
# broker_negotiator.py
#


"""
.. module:: broker_negotiator
.. role:: red

BitDust broker_negotiator() Automat

EVENTS:
    * :red:`connect-request`
"""


from automats import automat


_BrokerNegotiator = None


def A(event=None, *args, **kwargs):
    """
    Access method to interact with `broker_negotiator()` machine.
    """
    global _BrokerNegotiator
    if event is None:
        return _BrokerNegotiator
    if _BrokerNegotiator is None:
        # TODO: set automat name and starting state here
        _BrokerNegotiator = BrokerNegotiator(name='broker_negotiator', state='AT_STARTUP')
    if event is not None:
        _BrokerNegotiator.automat(event, *args, **kwargs)
    return _BrokerNegotiator


def Destroy():
    """
    Destroy `broker_negotiator()` automat and remove its instance from memory.
    """
    global _BrokerNegotiator
    if _BrokerNegotiator is None:
        return
    _BrokerNegotiator.destroy()
    del _BrokerNegotiator
    _BrokerNegotiator = None


class BrokerNegotiator(automat.Automat):
    """
    This class implements all the functionality of ``broker_negotiator()`` state machine.
    """

    def __init__(self, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `broker_negotiator()` state machine.
        """
        super(BrokerNegotiator, self).__init__(
            name="broker_negotiator",
            state="AT_STARTUP",
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs
        )

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `broker_negotiator()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `broker_negotiator()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `broker_negotiator()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---CUR_BROKER?---
        if self.state == 'CUR_BROKER?':
            if cur-broker-failed or cur-broker-timeout doVerifyPrevRecord():
                self.state = 'PLACE_EMPTY'
            elif cur-broker-ack:
                self.state = 'REJECT'
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'connect-request':
                self.state = 'DHT_VERIFY'
                self.doVerifyMyRecord(*args, **kwargs)
        #---DHT_VERIFY---
        elif self.state == 'DHT_VERIFY':
            if record-busy doVerifyThisRecord():
                self.state = 'PLACE_BUSY'
            elif record-own doVerifyPrevRecord():
                self.state = 'PLACE_OWN'
            elif record-empty doVerifyPrevRecord():
                self.state = 'PLACE_EMPTY'
        #---PLACE_BUSY---
        elif self.state == 'PLACE_BUSY':
            if this-record-valid doRequestThisBroker():
                self.state = 'CUR_BROKER?'
            elif this-record-invalid doRequestPrevBroker():
                self.state = 'PLACE_EMPTY'
        #---REJECT---
        elif self.state == 'REJECT':
            pass
        #---ACCEPT---
        elif self.state == 'ACCEPT':
            pass
        #---PLACE_OWN---
        elif self.state == 'PLACE_OWN':
            if parent-record-exist doRequestPrevBroker():
                self.state = 'PREV_BROKER?'
            elif parent-record-not-exist doHirePrevBroker():
                self.state = 'HIRE_PREV?'
            elif top-place-own:
                self.state = 'ACCEPT'
        #---PLACE_EMPTY---
        elif self.state == 'PLACE_EMPTY':
            if parent-record-exist doRequestPrevBroker():
                self.state = 'PREV_BROKER?'
            elif parent-record-not-exist doHirePrevBroker():
                self.state = 'HIRE_PREV?'
            elif top-place-empty:
                self.state = 'ACCEPT'
        #---PREV_BROKER?---
        elif self.state == 'PREV_BROKER?':
            if :
                self.state = 'ACCEPT'
            elif :
                self.state = 'HIRE_PREV?'
            elif prev-broker-ack:
                self.state = 'REJECT'
        #---HIRE_PREV?---
        elif self.state == 'HIRE_PREV?':
            if :
                self.state = 'ACCEPT'
            elif :
                self.state = 'REJECT'


    def doVerifyMyRecord(self, *args, **kwargs):
        """
        Action method.
        """

