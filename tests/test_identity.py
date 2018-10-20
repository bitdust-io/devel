from unittest import TestCase
import os


_some_priv_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA/ZsJKyCakqA8vO2r0CTOG0qE2l+4y1dIqh7VC0oaVkXy0Cim
s3N+NNt6vJ617H5FeMALasRf4+5nHkleTB+BKTKBxt4fLm9Mz3mkw8U+pstJfYzS
FjjG3Zjs6XC4HyMjOCTkYCdvQQTeqB9ALAJ10YpVwlJlXOaFoscwv3LkUD4XB2Q4
rh6iqYdQo7Na2vY0aAw+t/wTnLTzr/rxQuhbng7ktPv8ZUx69eHzG07gLRpqzYH7
zkvuijtesxPIFFLaSlgQPc3rILqwLP/wI6fDjtPWlnG1cJJ9e7PBq1LkQ8FJoCxa
Sx9/zrZcVuKFnCPGrc1hjqCIU9Hh3wTPxV/PIQIDAQABAoIBAAO2fZXPXf33WTj2
SpI4e2PqRVEduXAQ2AIwGNQX4T70j8A5C82Tpg7ObLYxWruICCVjJo5Oin1vpIbi
Ac66im68yTTnnyRJajynyh1jivtV3XPYatdlvJvFePNMZHtbDYa4AQ0wlJwVRFB+
LSIxJXIO94/pz9y3uLAEINWZCt31xEpIWiJYDYvOnu/SUNJ652WzmEoguzdYndam
PjoC8S4PUWslCeMiHc5XLhrZVXoNFQyqAX/zZoKLtbNQq0Z3Huguih0ID5oSFWMl
MeFLUoW2UAvo+dwkW5DJc5VyBFvAX/J+03WqvqmX0198mD8LrMDr9hGsIAyQmGud
oECFIZECgYEA/hm8SiLaMjhvtvhPDYKG7+RbEomdf2F1sSrJtyUCTCswKpjGwDnP
zcxDJuGzIRYw16GoUBWIcJfrDXzzNN6TxX9qXhd8uJ+VckEp7H1mOYLnLN5Ekjyu
XqrYzG/cSRqb1IESG3ikm8/587WxRA+4/rm+XWg1XZCOotiJrCdz6LECgYEA/4Ba
auGkYErkw2E02WMRqo2Ct2cfWPCRXy/oWSvbDxNlhFoheKr/6e9PHQ+m5iLDo3sq
3ZaPgfDaty6uI4v/rCwDGdv2s5bkI9crZ2DxNKhgJUE9No87jSSHjBMv0eylUBHA
DB5n1jyEYFHTGpy4Hvr6M6sCz/8Ehvga9J596XECgYAl4F4xytotjD4Szxaxk9hb
X/W3YK4Kc9OgUhl5ZFngUru+TcGqm7N/IMiNviz+bJlhOyaksWECL5MJEqwKIHd0
hBat6eBcgOU8/7upFdQsFHgzNvqPtd3kHKFub+otN3stBQRW9ffLhgfjLR08YP+Z
cMSQld0GkmrAmXiEIelkMQKBgQCnyIUX3ReRuHzjpQkMnJc0Vft6LvkR8eC1DoPZ
UwhmrQkkUf/a+whVejaM0gN662doCvEKVN3mqeEnHDt00nHSgZCDwcQPCU7GDn3N
RIcBWnTQ4jethX/I3y04Gj1z8KBapV1lV+4+bL1Nd05XEoWCqrP1jB6rsj8p1vH0
o8PxsQKBgFxHBaLtYSqwQoolo0mmpGCHTdfmn+bRQaqL3DQEGYULtkj+gGuqVlj6
5cnFfTRgzj81rSkJIg7ZQ+V3CvtZSjYnflN2L1IS1aT+N9uvoLSV/yzNLmHlG6nR
TjpvKeAap/ydSo6j8K97O8h4EeVKM2xfbNBVpv1mpR8AbkJf7Ioz
-----END RSA PRIVATE KEY-----"""

_some_identity_xml = """<?xml version="1.0" encoding="utf-8"?>
<identity>
  <sources>
    <source>http://127.0.0.1:8084/alice.xml</source>
  </sources>
  <contacts>
    <contact>tcp://127.0.0.1:7103</contact>
  </contacts>
  <certificates/>
  <scrubbers/>
  <postage>0</postage>
  <date>Oct 06, 2018</date>
  <version></version>
  <revision>0</revision>
  <publickey>ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQD9mwkrIJqSoDy87avQJM4bSoTaX7jLV0iqHtULShpWRfLQKKazc34023q8nrXsfkV4wAtqxF/j7mceSV5MH4EpMoHG3h8ub0zPeaTDxT6my0l9jNIWOMbdmOzpcLgfIyM4JORgJ29BBN6oH0AsAnXRilXCUmVc5oWixzC/cuRQPhcHZDiuHqKph1Cjs1ra9jRoDD63/BOctPOv+vFC6FueDuS0+/xlTHr14fMbTuAtGmrNgfvOS+6KO16zE8gUUtpKWBA9zesgurAs//Ajp8OO09aWcbVwkn17s8GrUuRDwUmgLFpLH3/OtlxW4oWcI8atzWGOoIhT0eHfBM/FX88h</publickey>
  <signature>906441963064925827454594808955119786427327091644004203121255573673324339896720684156436969809331302081059171001468697744607176215971850395448358447221987030255681283469602485017439100048818715591137645334649289784704347547476744833593959051239987455656492991690929110057776187651745011046495572223232179906271885029639566994962961751420295596050170876718201976232073313442092469148257068924122205928495395843354406033087633663157320015417942886925426409641297819144861516715728591303834175552581452070473350075769438068777969720417764064190628218036180170101856467748070658740635441921977032005183554438715223073852</signature>
</identity>"""


class Test(TestCase):

    def setUp(self):
        from logs import lg
        from main import settings
        from crypt import key
        from userid import my_id
        lg.set_debug_level(30)
        settings.init()
        self.my_current_key = None
        if key.isMyKeyExists():
            os.rename(settings.KeyFileName(), '/tmp/_current_priv_key')
        fout = open('/tmp/_some_priv_key', 'w')
        fout.write(_some_priv_key)
        fout.close()
        if my_id.isLocalIdentityExists():
            os.rename(settings.LocalIdentityFilename(), '/tmp/_current_localidentity')
        fout = open(settings.LocalIdentityFilename(), 'w')
        fout.write(_some_identity_xml)
        fout.close()
        self.assertTrue(key.LoadMyKey(keyfilename='/tmp/_some_priv_key'))
        self.assertTrue(my_id.loadLocalIdentity())

    def tearDown(self):
        from main import settings
        from crypt import key
        from userid import my_id
        key.ForgetMyKey()
        my_id.forgetLocalIdentity()
        if os.path.isfile('/tmp/_current_localidentity'):
            os.rename('/tmp/_current_localidentity', settings.LocalIdentityFilename())
        if os.path.isfile('/tmp/_current_priv_key'):
            os.rename('/tmp/_current_priv_key', settings.KeyFileName())
        os.remove('/tmp/_some_priv_key')

    def test_identity_valid(self):
        from userid import identity
        some_identity = identity.identity(xmlsrc=_some_identity_xml)
        self.assertTrue(some_identity.isCorrect())
        self.assertTrue(some_identity.Valid())

    def test_identity_not_valid(self):
        from userid import identity
        _broken_identity_xml = _some_identity_xml.replace('alice', 'bob')
        broken_identity = identity.identity(xmlsrc=_broken_identity_xml)
        self.assertTrue(broken_identity.isCorrect())
        self.assertFalse(broken_identity.Valid())
