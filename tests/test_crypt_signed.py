import os

from unittest import TestCase

from bitdust.logs import lg

from bitdust.system import bpio

from bitdust.main import settings

from bitdust.crypt import key
from bitdust.crypt import signed

from bitdust.contacts import identitycache

from bitdust.userid import identity
from bitdust.userid import my_id

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

_another_priv_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0K7W6mtHwNYTshIq9yfCR2Gi0U4rFPiAornvgltAUC+r68Ld
yb+r4WF/zSJ5uzwalrorajwOlZkvitBoadrdE0HhI7J9Dg0nuQ1OWLRoJk7wpeTm
6KJ5ZTudQnnaXC6hdr00/rOZMhr5JirYs6APUUANg1Pck1wJnmLO/ljDssVi+2zg
3g26omKpyq8VF29EH1r0mfEL6MH7pstTHZ/gyaW7dlN/VbgKr79Bp9IIaR4eX2nA
YNtQTVWErk3S0gI4tYjjejArj7PkkdQ+oVY3MEn5ywmsEUzb7StquoLlQb+ngwuk
GOom78PJa0Ax593ooToMRfKnjxIiiOvXo3TfhwIDAQABAoIBAAUVzZzmwlfbn50+
PhfJuz08Dtik2/3l1FSizUhS6u1JTBoxpG/vIMQcOR4JkgfS/h7gKICtN/nDQtpS
G8lAkRSQDWluRwfZoDctMNSOiN8uG0Ufn9TZaLXjzwA4se5/IGYhVDJEtB35dErO
znsKEnV7ZxjlKUHaA039wGeISDSJ+YyXfgDGoImLNO/2heGAQGnnf8/oSBCfGKt3
jUyZ9ZtEXCx8W0RXofLQbw/rvU2kiQk57yoEB1yr36d6wJtwYcg1REQmEDVVK7lj
/oe1kdyoRv7qUc/eHatxd0AZ3Q7K+ZNTg6JkkA0h97LI/rx9HyzsgBp2lWboo+KN
0C0VoBECgYEA5L1VYFtjEdHA9r76r5vaf3QKqCY7o0W0lwOuQZPRTrQZwqH9T5T3
x+rO/SfM1m3DqzZIx5jOxXvric5+2xlVrTkm2sDI5IUkMeC0gULaUmoUbMVr8dxk
tQ3AgRg0eQBrJsR3vq+IA1GLASO19dsc9qNYSDREesJClhnXsK1TRl8CgYEA6Y2Y
IMScBZoCmqcfV4hiSYiK2pLKu7ArzbQ67ADeaDWcu56NDIj7hoE6/MnzXa7Bag/O
WrusyELed18FncMYZEcnxNm7N7/M7HhsNz66esd4IZb1S5G7gI0pZhjADO5zD68s
qzzJyEup+0tvs451qGgNhgngNdu2QQ+/jogyZ9kCgYAUvhKa7U6blBDSj1j+SbzT
p/s7alQoJy8MLrpDmhr17yES5EurRs/9Yg6pKE3L+CIxSXfqGbJOeEFQutgIGFEL
p04dsjPFfUld+ImF20EfDh2SC4kRYrIDNR8K1d4URvRwjIprUVGdM2zOiqV6iQck
WoWr7olzNGCDag6EKAOQMwKBgHO78tLqGta7xuaUQnfB4dLGkuhVLZlsZ4h782bX
116UkqJ2oza++sVgbLav7KVT4AyK4JsdvTVPzaYhtErFTuUCTbbCnn+1z/qughGu
SAJnriQXBl74TI4bZZRuV10RHHt9Nwl0ChnzRLx+WVAFHFDjny/43N5TjjEXeLlM
zI2hAoGBAL0vdtKLms6VKjzbMrJQCWw0DKDM6I4i8nwzwZq3mrSl9txhbBv4rMYL
cTi9rfqtYAyPv56URRfQLlfKXKDgW0VFCjrHJxlk00v3daKaE6Hm7pc5dyEIOlaQ
15lHS41L0cAm0JvYaxWSRTcD+o5YDjzzHOMAOMa5WOB8Gct5c2LH
-----END RSA PRIVATE KEY-----"""

_another_identity_xml = """<?xml version="1.0" encoding="utf-8"?>
<identity>
  <sources>
    <source>http://127.0.0.1/bob.xml</source>
  </sources>
  <contacts>
    <contact>tcp://127.0.0.1:7084</contact>
  </contacts>
  <certificates/>
  <scrubbers/>
  <postage>1</postage>
  <date>Oct 24, 2019</date>
  <version></version>
  <revision>0</revision>
  <publickey>ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDQrtbqa0fA1hOyEir3J8JHYaLRTisU+ICiue+CW0BQL6vrwt3Jv6vhYX/NInm7PBqWuitqPA6VmS+K0Ghp2t0TQeEjsn0ODSe5DU5YtGgmTvCl5OboonllO51CedpcLqF2vTT+s5kyGvkmKtizoA9RQA2DU9yTXAmeYs7+WMOyxWL7bODeDbqiYqnKrxUXb0QfWvSZ8Qvowfumy1Mdn+DJpbt2U39VuAqvv0Gn0ghpHh5facBg21BNVYSuTdLSAji1iON6MCuPs+SR1D6hVjcwSfnLCawRTNvtK2q6guVBv6eDC6QY6ibvw8lrQDHn3eihOgxF8qePEiKI69ejdN+H</publickey>
  <signature>7118061957075453696716322402549873629583090531377829787358943853512068040987164498407766674184560342298357623634868359334229162508919786815142935647261418875317697547998568533174340416921174048272451734175433580589302993305856695340396044096681890805130255873251587810038693862249566606578221713897721428943492189359774852111859449335038229526841036388944975118276591256609534252009152474480757561255525458912203902903374225748071040925567057812536965407030052862209122393308650557621603597311938572665997436602400523895745490032603668957797406619611076062671815272880277770486073473230719226178569117607225876297792</signature>
</identity>"""


class Test(TestCase):

    def setUp(self):
        try:
            bpio.rmdir_recursive('/tmp/.bitdust_tmp')
        except Exception:
            pass
        lg.set_debug_level(30)
        settings.init(base_dir='/tmp/.bitdust_tmp')
        self.my_current_key = None
        try:
            os.makedirs('/tmp/.bitdust_tmp/default/metadata/')
        except:
            pass
        try:
            os.makedirs('/tmp/.bitdust_tmp/identitycache/')
        except:
            pass
        fout = open(settings.KeyFileName(), 'w')
        fout.write(_some_priv_key)
        fout.close()
        fout = open(settings.LocalIdentityFilename(), 'w')
        fout.write(_some_identity_xml)
        fout.close()
        self.assertTrue(key.LoadMyKey())
        self.assertTrue(my_id.loadLocalIdentity())
        self.bob_ident = identity.identity(xmlsrc=_another_identity_xml)
        identitycache.UpdateAfterChecking(idurl=self.bob_ident.getIDURL(), xml_src=_another_identity_xml)

    def tearDown(self):
        key.ForgetMyKey()
        my_id.forgetLocalIdentity()
        settings.shutdown()
        bpio.rmdir_recursive('/tmp/.bitdust_tmp')

    def test_signed_packet(self):
        key.InitMyKey()
        payload_size = 1024
        attempts = 10
        for i in range(attempts):
            data1 = os.urandom(payload_size)
            p1 = signed.Packet(
                'Data',
                my_id.getIDURL(),
                my_id.getIDURL(),
                'SomeID',
                data1,
                self.bob_ident.getIDURL(),
            )
            self.assertTrue(p1.Valid())
            raw1 = p1.Serialize()
            p2 = signed.Unserialize(raw1)
            self.assertTrue(p2.Valid())
