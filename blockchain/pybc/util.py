"""
util.py: PyBC utility functions.

Contains functions for converting among bytestrings (strings that are just
arrays of bytes), strings (strings that are actaul character data) and other
basic types.

Also contains a useful function for setting up logging.

"""

import base64
import binascii
import time
import logging


def bytes2string(bytestring, limit=None):
    """
    Encode the given byte string as a text string. Returns the encoded string.

    """
    if not bytestring:
        return bytestring
    if limit:
        return base64.b64encode(bytestring)[:limit]
    return base64.b64encode(bytestring)


def string2bytes(string):
    """
    Decode the given printable string into a byte string. Returns the decoded
    bytes.

    """
    if not string:
        return string
    return base64.b64decode(string)


def bytes2hex(bytestring):
    """
    Encode the given bytestring as hex.

    """
    if not bytestring:
        return bytestring
    return "".join("{:02x}".format(ord(char)) for char in bytestring)


def bytes2long(s):
    """
    Decode a Python long integer (bigint) from a string of bytes.

    See http://bugs.python.org/issue923643

    """
    return long(binascii.hexlify(s), 16)


def long2bytes(n):
    """
    Encode a Python long integer (bigint) as a string of bytes.

    See http://bugs.python.org/issue923643

    """

    hexstring = "%x" % n

    if len(hexstring) % 2 != 0:
        # Pad to even length, big-endian.
        hexstring = "0" + hexstring

    return binascii.unhexlify(hexstring)


def time2string(seconds):
    """
    Given a seconds since epock int, return a UTC time string.

    """

    return time.strftime("%d %b %Y %H:%M:%S", time.gmtime(seconds))


def set_loglevel(loglevel, logformat="%(levelname)s:%(message)s", logdatefmt="%H:%M:%S", logfilename=None):
    """
    Given a string log level name, set the logging module's log level to that
    level. Raise an exception if the log level is invalid.

    """

    # Borrows heavily from (actually is a straight copy of) the recipe at
    # <http://docs.python.org/2/howto/logging.html>

    # What's the log level number from the module (or None if not found)?
    numeric_level = getattr(logging, loglevel.upper(), None)

    if not isinstance(numeric_level, int):
        # Turns out not to be a valid log level
        raise ValueError("Invalid log level: {}".format(loglevel))

    # Set the log level to the correct numeric value
    logging.basicConfig(format=logformat, level=numeric_level, datefmt=logdatefmt, filename=logfilename, filemode='w')
