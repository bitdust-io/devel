from Crypto.PublicKey import DSA, RSA


class BadKeyError(Exception):
    """
    Raised when a key isn't what we expected from it.
    """


class KeyObjectWrapper:
    def __init__(self, key):
        """
        :param twisted.conch.ssh.keys.Key key:
        """
        self.key = key

    @property
    def keyObject(self):
        """
        A C{Crypto.PublicKey} object similar to this key.

        As PyCrypto is no longer used for the underlying operations, this
        property should be avoided.
        """
        keyType = self.key.type()
        keyData = self.key.data()
        isPublic = self.key.isPublic()

        if keyType == 'RSA':
            if isPublic:
                keyObject = RSA.construct((
                    keyData['n'],
                    long(keyData['e']),
                ))
            else:
                keyObject = RSA.construct((
                    keyData['n'],
                    long(keyData['e']),
                    keyData['d'],
                    keyData['p'],
                    keyData['q'],
                    keyData['u'],
                ))
        elif keyType == 'DSA':
            if isPublic:
                keyObject = DSA.construct((
                    keyData['y'],
                    keyData['g'],
                    keyData['p'],
                    keyData['q'],
                ))
            else:
                keyObject = DSA.construct((
                    keyData['y'],
                    keyData['g'],
                    keyData['p'],
                    keyData['q'],
                    keyData['x'],
                ))
        else:
            raise BadKeyError('Unsupported key type.')

        return keyObject
