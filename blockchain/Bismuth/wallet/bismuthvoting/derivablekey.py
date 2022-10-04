"""
A DerivableKey class for use with the Bismuth Governance Voting Protocol.
"""

import hmac
from hashlib import sha256, sha512

from bismuthvoting.bip39 import BIP39
from coincurve import PrivateKey
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
from six import int2byte

__version__ = "0.0.4"


FIELD_ORDER = 2**256


# from ecdsa.ecdsa
def int_to_string(x):
    """Convert integer x into a string of bytes, as per X9.62."""
    assert x >= 0
    if x == 0:
        return b"\0"
    result = []
    while x:
        ordinal = x & 0xFF
        result.append(int2byte(ordinal))
        x >>= 8

    result.reverse()
    return b"".join(result)


def string_to_int(s):
    """Convert a string of bytes into an integer, as per X9.62."""
    result = 0
    for c in s:
        if not isinstance(c, int):
            c = ord(c)
        result = 256 * result + c
    return result


def random_padding(data: bytes, block_size: int = 16, pad_with_zeros=False) -> bytes:
    padding_len = block_size - len(data) % block_size
    if pad_with_zeros:
        padding = b"\x00" * padding_len
    else:
        padding = get_random_bytes(padding_len)
    return data + padding


class DerivableKey:
    def __init__(self, entropy: bytes = None, seed: bytes = None):
        if seed is None:
            # reconstruct seed from entropy via BIP39
            assert entropy is not None
            bip39 = BIP39(entropy)
            self.seed = bip39.to_seed()
        else:
            self.seed = seed
        # seed is a 512 bits (kpar, cpar) privkey, code

    def to_pubkey(self) -> bytes:
        """Computes and sends back pubkey, point(kpar) of current key(kpar)"""
        kpar = PrivateKey.from_hex(self.seed[:32].hex())
        K = kpar.public_key.format(compressed=False)
        return K

    def to_aes_key(self) -> bytes:
        """Returns sha256 hash of the pubkey, to use as AES key"""
        pubkey = self.to_pubkey()
        return sha256(pubkey).digest()

    def derive(self, s: str) -> "DerivableKey":
        """Derive with given buffer"""
        data = self.to_pubkey().hex() + s
        # print("data", data.encode("utf-8").hex())
        I = hmac.new(self.seed[32:], data.encode("utf-8"), sha512).digest()
        IL, IR = I[:32], I[32:]
        # print("IL", IL.hex())
        # print("seed", self.seed[:32].hex())
        ks_int = (string_to_int(IL) + string_to_int(self.seed[:32])) % FIELD_ORDER
        ks = int_to_string(ks_int)
        # print("ks_hex", ks.hex())
        cs = IR
        return DerivableKey(seed=ks + cs)

    @classmethod
    def encrypt(cls, aes_key: bytes, data: bytes, iv: bytes) -> bytes:
        assert len(aes_key) == 32
        # AES is stateful, needs one instance per operation
        print("aes key", aes_key.hex())
        print("aes data", data.hex())
        print("aes iv", iv.hex())
        aes = AES.new(aes_key, AES.MODE_CBC, iv=iv)
        encrypted = aes.encrypt(data)
        return encrypted

    @classmethod
    def encrypt_vote(
        cls, aes_key: bytes, data: str, pad_with_zeroes=False, iv: bytes = None
    ) -> bytes:
        """Dedicated method to encrypt vote message"""
        # Add space to vote option
        data += " "
        data = data.encode("utf-8")
        # Pad to 16 bytes -
        data = random_padding(data, 16, pad_with_zeros=pad_with_zeroes)
        if iv is None:
            # iv is needed for CBC, we use a fixed iv - 16 bytes long - to limit data to transmit by default.
            iv = "Bismuth BGVP IV.".encode("utf-8")
        return cls.encrypt(aes_key, data, iv)

    @classmethod
    def decrypt(cls, aes_key: bytes, data: bytes, iv: bytes) -> bytes:
        assert len(aes_key) == 32
        # AES is stateful, needs one instance per operation
        aes = AES.new(aes_key, AES.MODE_CBC, iv=iv)
        clear = aes.decrypt(data)
        return clear

    @classmethod
    def decrypt_vote(cls, aes_key: bytes, data: bytes, iv: bytes = None) -> str:
        """Dedicated method to decrypt vote message"""
        if iv is None:
            # iv is needed for CBC, we use a fixed iv - 16 bytes long - to limit data to transmit by default.
            iv = "Bismuth BGVP IV.".encode("utf-8")
        clear = cls.decrypt(aes_key, data, iv=iv)
        # print(clear)
        clear, _ = clear.split(b" ", 1)
        return clear.decode("utf-8")

    @classmethod
    def get_from_path(cls, mnemonic: str, path: str) -> "DerivableKey":
        """Gets the derived key in one go from address/motion path string"""
        elements = path.split("/")
        address = elements.pop(0)
        motion = "/".join(elements)
        bip39 = BIP39.from_mnemonic(mnemonic)
        master_key = DerivableKey(seed=bip39.to_seed())
        address_key = master_key.derive(address)
        motion_key = address_key.derive(motion)
        return motion_key
