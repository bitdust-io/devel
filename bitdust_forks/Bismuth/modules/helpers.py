"""
Helpers for the wallet server

Mainly from bismuth core code
"""

import re
from decimal import Decimal

__version__ = '0.0.4'

DECIMAL_ZERO_2DP = Decimal('0.00')
DECIMAL_ZERO_8DP = Decimal('0.00000000')
DECIMAL_ZERO_10DP = Decimal('0.0000000000')


def quantize_two(value):
    value = Decimal(value)
    value = value.quantize(DECIMAL_ZERO_2DP)
    return value


def quantize_eight(value):
    value = Decimal(value)
    value = value.quantize(DECIMAL_ZERO_8DP)
    return value


def quantize_ten(value):
    value = Decimal(value)
    value = value.quantize(DECIMAL_ZERO_10DP)
    return value


def replace_regex(string, replace):
    replaced_string = re.sub(r'^{}'.format(replace), '', string)
    return replaced_string


def fee_calculate(openfield, operation='', block=0):
    return quantize_eight(Decimal('0.00'))
    # block var will be removed after HF
    fee = Decimal('0.01') + (Decimal(len(openfield))/Decimal('100000'))  # 0.01 dust
    if operation == 'token:issue':
        fee = Decimal(fee) + Decimal('10')
    if openfield.startswith('alias='):
        fee = Decimal(fee) + Decimal('1')
    return quantize_eight(fee)


# Dup code, not pretty, but would need address module to avoid dup

RE_RSA_ADDRESS = re.compile(r'^[abcdef0123456789]{56}$')
# TODO: improve that ECDSA one
RE_ECDSA_ADDRESS = re.compile(r'^Bis')


def address_validate(address):
    if RE_RSA_ADDRESS.match(address):
        # RSA, 56 hex
        return True
    elif RE_ECDSA_ADDRESS.match(address):
        if 50 < len(address) < 60:
            # ED25519, around 54
            return True
        if 30 < len(address) < 50:
            # ecdsa, around 37
            return True
    return False
