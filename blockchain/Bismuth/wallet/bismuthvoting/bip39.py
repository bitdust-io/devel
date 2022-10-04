"""
A Simple wrapper around BIP39 Mnemonic module to have a simple consistent interface in case of future module swap.
"""

from mnemonic import Mnemonic

__version__ = "0.0.1"


DEFAULT_PASSPHRASE = "BismuthGVP"


class BIP39:
    def __init__(self, entropy: bytes = None):
        self.mnemonic = Mnemonic("english")
        self.entropy = entropy

    def to_mnemonic(self) -> str:
        return self.mnemonic.to_mnemonic(self.entropy)

    def to_seed(self, mnemonic: str = None, passphrase: str = None) -> bytes:
        mnemonic = self.to_mnemonic() if mnemonic is None else mnemonic
        passphrase = DEFAULT_PASSPHRASE if passphrase is None else passphrase
        return self.mnemonic.to_seed(mnemonic, passphrase)

    @classmethod
    def check(cls, mnemonic: str) -> bool:
        return Mnemonic("english").check(mnemonic)

    @staticmethod
    def from_mnemonic(mnemonic: str) -> "BIP39":
        mnemo = Mnemonic("english")
        entropy = mnemo.to_entropy(mnemonic)
        return BIP39(entropy)
