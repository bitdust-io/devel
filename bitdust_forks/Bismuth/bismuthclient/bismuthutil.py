"""
Generic helpers  Bismuth
"""

import re
import hashlib
import base64
import polysign.signerfactory
from decimal import Decimal
from Cryptodome.Random import get_random_bytes
from random import randint


__version__ = '0.0.7'


def checksum(string, legacy=True):
    """ Base 64 checksum of MD5. Used by bisurl"""
    if legacy:
        m = hashlib.md5()
        m.update(string.encode("utf-8"))
        return base64.b85encode(m.digest()).decode("utf-8")
    else:
        m = hashlib.blake2b(digest_size=4)
        m.update(string.encode("utf-8"))
        return base64.urlsafe_b64encode(m.digest()).decode("utf-8")


class BismuthUtil():
    """Static helper utils"""

    @staticmethod
    def valid_address(address: str):
        return polysign.signerfactory.SignerFactory.address_is_valid(address)

    @staticmethod
    def fee_for_tx(openfield: str = '', operation: str = '', block: int = 0) -> Decimal:
        # block var will be removed after HF
        fee = Decimal("0.01") + (Decimal(len(openfield)) / Decimal("100000"))  # 0.01 dust
        if operation == "token:issue":
            fee = Decimal(fee) + Decimal("10")
        if openfield.startswith("alias="):
            fee = Decimal(fee) + Decimal("1")
        # if operation == "alias:register": #add in the future, careful about forking
        #    fee = Decimal(fee) + Decimal("1")
        return fee.quantize(Decimal('0.00000000'))

    @staticmethod
    def height_to_supply(height):
        """Gives total supply at a given block height"""
        if height <= 1450000:
            R0 = 11680000.4
            delta = 2e-6
            pos = 0.8
            pow = 12.6
            N = height - 8e5
            dev_rew = 1.1
            R = dev_rew * R0 + N * (pos + dev_rew * (pow - N / 2 * delta))
        else:
            # select sum(reward) from transactions where block_height>0 and block_height<=1450000;
            R0 = 19061426.9635592
            # select sum(amount) from transactions where recipient='3e08b5538a4509d9daa99e01ca5912cda3e98a7f79ca01248c2bde16' and block_height>=-1450000;
            R1 = 920008
            delta1 = 91e-8
            delta2 = 33e-8
            pos = 2.4
            pow = 5.5
            N = height - 1450000
            dev_rew = 1.1
            R = dev_rew * R0 + R1 + N * ((pos - N / 2 * delta2) + dev_rew * (pow - N / 2 * delta1))
        return R


    @staticmethod
    def create_bis_url(recipient, amount, operation, openfield, legacy=True):
        """
        Constructs a bis url from tx elements, v2
        """
        if legacy:
            """
            Constructs a bis url from tx elements
            """

            # Only command supported so far.
            command = "pay"
            openfield_b85_encode = base64.b85encode(openfield.encode("utf-8")).decode("utf-8")
            operation_b85_encode = base64.b85encode(operation.encode("utf-8")).decode("utf-8")
            url_partial = "bis://{}/{}/{}/{}/{}/".format(command, recipient, amount,
                                                         operation_b85_encode, openfield_b85_encode)
            url_constructed = url_partial + checksum(url_partial)
            return url_constructed

        else:
            openfield_b64_encode = base64.urlsafe_b64encode(openfield.encode("utf-8")).decode("utf-8")
            operation_b64_encode = base64.urlsafe_b64encode(operation.encode("utf-8")).decode("utf-8")
            url_partial = "bis://{}/{}/{}/{}/".format(recipient, amount,
                                                      operation_b64_encode, openfield_b64_encode)
            url_constructed = url_partial + checksum(url_partial, legacy=False)
            return url_constructed

    @staticmethod
    def read_url(url, legacy=True):
        """
        Takes a bis url, checks its checksum and gives the components, v2
        """
        if legacy:
            url_split = url.split("/")
            reconstruct = "bis://{}/{}/{}/{}/{}/".format(url_split[2], url_split[3], url_split[4],
                                                         url_split[5], url_split[6], url_split[7])
            operation_b85_decode = base64.b85decode(url_split[5]).decode("utf-8")
            openfield_b85_decode = base64.b85decode(url_split[6]).decode("utf-8")

            if checksum(reconstruct) == url_split[7]:
                url_deconstructed = {"recipient": url_split[3], "amount": url_split[4],
                                     "operation": operation_b85_decode,
                                     "openfield": openfield_b85_decode}
                return url_deconstructed
            else:
                return {'Error': 'Checksum failed'}

        else:
            url_split = url.split("/")
            reconstruct = "bis://{}/{}/{}/{}/".format(url_split[2], url_split[3], url_split[4],
                                                      url_split[5], url_split[6])
            operation_b64_decode = base64.urlsafe_b64decode(url_split[4]).decode("utf-8")
            openfield_b64_decode = base64.urlsafe_b64decode(url_split[5]).decode("utf-8")

            if checksum(reconstruct, legacy=False) == url_split[6]:
                url_deconstructed = {"recipient": url_split[2], "amount": url_split[3],
                                     "operation": operation_b64_decode,
                                     "openfield": openfield_b64_decode}
                return url_deconstructed
            else:
                return {'Error': 'Checksum failed'}

    @staticmethod
    def protocol_controller(url):
        """ Returns version of protocol. v1 = base85 and command, v2 = just base64, no command"""
        split = url.split("/")
        if split[2] == "pay":
            return BismuthUtil.read_url(url, legacy=True)
        else:
            return BismuthUtil.read_url(url, legacy=False)

    @staticmethod
    def sublimate(key: str, parts_count: int) -> dict:
        """Not optimized. xor key splitting with keylen entropy"""
        try:
            # If hex only, encode as binary
            key = bytes.fromhex(key)
        except Exception as e:
            # else as is
            key = key.encode()
        seed = randint(100, 200)
        _ = get_random_bytes(seed)
        key_len = len(key)
        parts = []
        for i in range(parts_count -1):
            parts.append(get_random_bytes(key_len))
        parts.append(key)  # last one
        final = b""
        for i in range(key_len):
            temp = parts[0][i]
            for j in range(1, parts_count):
                temp = temp ^ parts[j][i]
            final += temp.to_bytes(1, byteorder="big")
        parts[parts_count - 1] = final
        hash = hashlib.blake2b(digest_size=4)
        hash.update(key)
        return {"count": parts_count, "parts": parts, "hash": hash.hexdigest()}

    @staticmethod
    def condensate(parts: tuple) -> str:
        key_len = len(parts[0])
        parts_count = len(parts)
        final = b""
        for i in range(key_len):
            temp = parts[0][i]
            for j in range(1, parts_count):
                temp = temp ^ parts[j][i]
            final += temp.to_bytes(1, byteorder="big")
        hash = hashlib.blake2b(digest_size=4)
        hash.update(final)
        try:
            # Try to interpret as text
            final = final.decode()
        except Exception as e:
            # if not, was binary
            final = final.hex()
        return {"key": final, "hash": hash.hexdigest()}


if __name__ == "__main__":
    # tests
    url = BismuthUtil.create_bis_url("recipient", 2, "operation", "openfield", legacy=False)
    print(url)

    url_legacy = BismuthUtil.create_bis_url("recipient", 2, "operation", "openfield")
    print(url_legacy)

    read = BismuthUtil.read_url(url, legacy=False)
    print(read)

    print(BismuthUtil.protocol_controller(url))
    print(BismuthUtil.protocol_controller(url_legacy))

    print(BismuthUtil.valid_address("fail"))
    print(BismuthUtil.valid_address("60ce6a0b6b6076873c17ceaa5515c170d20c2ba3cb4de7f0ce722e92"))
