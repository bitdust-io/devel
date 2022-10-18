from unittest import TestCase

from bitdust.crypt import rsa_key
from bitdust.crypt import cipher


class Test(TestCase):

    def test_generate_sign_verify(self):
        msg = b'1234567890ABCDEFGH'
        k1 = rsa_key.RSAKey()
        k1.generate(1024)
        sig = k1.sign(msg)
        assert k1.verify(sig, msg, signature_as_digits=True)
        k2 = rsa_key.RSAKey()
        k2.fromString(k1.toPublicString())
        assert k2.verify(sig, msg) is True
        sig_raw = k1.sign(msg, as_digits=False)
        assert k2.verify(sig_raw, msg, signature_as_digits=False) is True

    def test_many_times(self):
        for _ in range(10):
            k1 = rsa_key.RSAKey()
            k1.generate(1024)

            k2 = rsa_key.RSAKey()
            k2.fromString(k1.toPublicString())

            for _ in range(100):
                msg = cipher.make_key()
                sig = k1.sign(msg)
                if not k2.verify(sig, msg):
                    assert False, (k1.toPrivateString(), msg, sig)

    def test_signature_begins_with_zero_byte(self):
        pk = '''-----BEGIN RSA PRIVATE KEY-----
MIICXQIBAAKBgQDrwjGUyNKFsrZzyxlfdFkStPWokQsKqjlR77xre6shrRJxfbHm
aweImvH9+x0on30ORLjk2PeVa2tp+z7hn35wS8VBx+lKOrCHDPPq5uZuNLD1KJHN
slzWzCxnquHVbrbop533S90ZA4IEi5SP/NkPjv8O/dm2JQfZTBLnum7GeQIDAQAB
AoGABESrRiDOouoF4JnMN0yxciPBkNAzbXmAeSnIdP+zrPPnshNO/bdxVvlLKUh7
Eim1B2WaHVaKQPPFaZFJZadQECqBM4DlxbyPN/7Xj59A5WeTMRw0eBnBq2IXmVzy
WVlW/Uy0cB+vxWj2YDo5+QI5UZ2GkZMZ57SrmiNOuAtUoUkCQQDwS6ZuFTft+de5
vdrXjhft0ahsecGTKg08sEFjHTwI9UPMIr1T9ZYjmYIzTLcEls3uVXRQulN8VeaD
r5WpYBZdAkEA+yqi/TUihJryoRatY7Qb63oRbD7RfoGeItpyU3stQrrs4SXSe/j3
jP6VauaYvRHaT9IJpgHCjF0yIMXY6AZ2zQJACbZ1FrQC27qijp5u7xGORA2aajAN
s/4aJN7W9cOjvpTzVZf94RvnIq88xQgPyb6yujR4DB9L6pWqSJ5bRUpd/QJBAPp0
JrlFbdk7RWx614WPiTPDsnH1JiP3DoCEwfIa5yQej61ncL9soTV4e/hwX6hRkBd+
Q17FbIFZQW5Ku6OLJpUCQQDuJl6KW8e5fXaaGlOP8R8N1oidSf5Sz2LM04GIi2Pa
iDt483pngPnWcya4OTjsvJ74yPtkDlwXuA43PUah56LG
-----END RSA PRIVATE KEY-----'''
        k = rsa_key.RSAKey()
        k.fromString(pk)
        msg = b'\xcf=8!7f\x85\x81\x05lc\xb1\xaas\x99\xda'
        sig = k.sign(msg)
        assert k.verify(sig, msg)
        sig_raw = k.sign(msg, as_digits=False)
        assert sig_raw[0:1] == b'\x00', sig_raw
        assert k.verify(sig_raw, msg, signature_as_digits=False)
