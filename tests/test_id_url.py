import tempfile
from unittest import TestCase

from logs import lg

from userid import id_url
from userid import identity


alice_bin = b'http://127.0.0.1:8084/alice.xml'
alice_text = 'http://127.0.0.1:8084/alice.xml'
bob = 'http://127.0.0.1/bob.xml'
carl = 'http://127.0.0.1/carl.xml'
dave = b'http://127.0.0.1:8084/dave.xml'
ethan_bin = b'http://127.0.0.1:8084/ethan.xml'
ethan_text = 'http://127.0.0.1:8084/ethan.xml'
ethan_not_exist = 'http://not-exist.com/ethan.xml'
frank_1 = 'http://source_one.com/frank.xml'
frank_2 = 'http://source_two.net/frank.xml'
george_1 = 'http://source_one.com/george.xml'
george_2 = 'http://source_two.net/george.xml'
george_3 = 'http://source_3.org/george.xml'


class TestIDURL(TestCase):

    def setUp(self):
        lg.set_debug_level(30)
        id_url._IdentityHistoryDir = tempfile.mkdtemp()
        id_url.init()

    def tearDown(self):
        id_url.shutdown()

    def _cache_identity(self, idname='alice'):
        known = {
            'alice': """<?xml version="1.0" encoding="utf-8"?>
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
                </identity>""",
            'bob': """<?xml version="1.0" encoding="utf-8"?>
                <identity>
                  <sources>
                    <source>http://127.0.0.1/bob.xml</source>
                  </sources>
                  <contacts>
                    <contact>tcp://:7592</contact>
                  </contacts>
                  <certificates/>
                  <scrubbers/>
                  <postage>1</postage>
                  <date>May 29, 2019</date>
                  <version></version>
                  <revision>0</revision>
                  <publickey>ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCewFs0xQAgdUXI0tzgWco6I4m47UCwvQTXs0fwF3gH+x+iAgx2RgTvjFpURyZPK45IrfF1kWvAE66ztzy2j+6hhHBXw58M3mj8zquDEKa+4mZFZdUtYRm6mNR7CfC9Nbot6wV52bHxsiLUxQvbBnc57lY/eMErXZSbUJjTjryCfVn7t5RS5aALQBfIVMfNMaVCJ3e5Rye0dhR6T9ZFjrLkReuo0okpCvoZZOkDIP1jLCjcOTv8uLUv+drqf8NIrZIj4pEF8rdRNujaocfiNThgkCBdmIhVrgkfIdK3vWM6QhJ3kZtulth1tDV5BK8/lfFZaPxfFGweR1/Gg9QDpOD9</publickey>
                  <signature>2555721207758289999127178087506098515147593088396681387272515731590789858885100168022894000811640385932332602114921724686816736386919493342116388342389202634533573440585853004416336080009871348355034060900570108740776929249059366125313043773781172121438059275318503578278037211137723742166236250810224379701898784507989109650122280574248889624793623753363750956166337580150155645791129345184984075393339236370769934887288067282063889985832781680930818596333533250385870238328128795908788457961092966872255919485411937392364346156912286424098295431775553440859616188700512071957957128388244692261317739667793487752010</signature>
                </identity>""",
            'carl': """<?xml version="1.0" encoding="utf-8"?>
                <identity>
                  <sources>
                    <source>http://127.0.0.1/carl.xml</source>
                  </sources>
                  <contacts>
                    <contact>tcp://:7592</contact>
                  </contacts>
                  <certificates/>
                  <scrubbers/>
                  <postage>1</postage>
                  <date>May 29, 2019</date>
                  <version></version>
                  <revision>0</revision>
                  <publickey>ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC36qNFejdTYd1GhNY8OW4Qyl5T9invqwF9/4AIjQX2r2bpqUj6imw+3H+EtELezUGuPEE7HBN2CXVIkvfz19L4nyLtHgmEgS8urX6DZl33fRmoJ17kKzU/64c1zijo+XbKfbAoEqWnY3PSUSDPSjOCYCAfLweVc6iwAK50Spoi8i5jh4qu6Oo5Suk9JU3IPNyoCY0jwxyG2pXOF5UKPaZLZnpTkbaiLINGlBHrOR+6pfIt0ab1G1IAOdz7ylakRDIiOLqWT6q8vgWyYFilSk3wb/iSu5oXfwSY7lLJlMY1xMz+gK+O7EyJ8aoxQGVZKmheNAQI0iQe8K0CVYepzsmv</publickey>
                  <signature>5671990383316217799860037685304343495387058906806556711839691386733274913975789513413370897454962593040260737131290348634715962286536496049223361697406163016265431897815056269698855557291580855474900681189364651092579128930585955713599705768551842925654460065820160273829629149488996975869038456697474472203533938277041514807958092108274858796695674035784529088500884603138043464155211422881469779643934748226157422190975487363378050151604507805760469094648075872918761427451548300297228184991006257005174164375453061839910123595693965585658191650111516102856331851331452134501115435806747753564318702409801372882796</signature>
                </identity>""",
            'frank': """<?xml version="1.0" encoding="utf-8"?>
                <identity>
                  <sources>
                    <source>http://source_one.com/frank.xml</source>
                    <source>http://source_two.net/frank.xml</source>
                  </sources>
                  <contacts>
                    <contact>tcp://:7592</contact>
                  </contacts>
                  <certificates/>
                  <scrubbers/>
                  <postage>1</postage>
                  <date>May 30, 2019</date>
                  <version></version>
                  <revision>0</revision>
                  <publickey>ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC/nDAJOYUyFnT5lVjwKPNYUGW5NJYQvzi8wautEPUG8ugN1ZkbRnZBJ46pJwaUIW1gUlJzL7bORi/Wy5tzAcvkWuFhDw+86w8Ex9r2X2Nrgr5cavueze11oOQ37SKFPDrZTYjhq2ed+rTSVJ42rylER9riAysJl1RAr6MsC7QtZ1KZDIWDzPQ7WQrvcoFVLK5o/paIsYLZcTccOALyS9CvXrNS9nYibU3Pyaq/zMHpFWY4nPAT7B0klyGiJzAHqTw1dNbAypXvnLVTG4eNKMbArXUpCHeDDY53tlnYkNDzuceB2lz86NpA2Ewx5Lr0w3/9N9yHsWgkYwNS/JfTD3bX</publickey>
                  <signature>1470399213647704633900402631360190748435234657805006286636791463584064835488129632598194044665351596044943525434240751740260636768475013148198222238722883426082432682475514476350120815733632509582355723720357735336589375729701597306429832373309354454899504698264706992923925941564707082145998420064958807862379138356373859695029687660005618278346183697586798708643920788468297695914337947578382893671765602095325079806610626195889332254501099459474380009351208434503202002631112285047914334438054000200851146620696476908095380446889155676867174774326398005266101164712932326179585975162203098025117398260191052011443</signature>
                </identity>""",
            'george': """<?xml version="1.0" encoding="utf-8"?>
                <identity>
                  <sources>
                    <source>http://source_one.com/george.xml</source>
                    <source>http://source_two.net/george.xml</source>
                    <source>http://source_3.org/george.xml</source>
                  </sources>
                  <contacts>
                    <contact>tcp://:7592</contact>
                  </contacts>
                  <certificates/>
                  <scrubbers/>
                  <postage>1</postage>
                  <date>May 30, 2019</date>
                  <version></version>
                  <revision>0</revision>
                  <publickey>ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC/IiHo/Nczuyzkd+0x4CUrzIO0iQyBAOdQZ3SRfgECfsYFemS7oYqp2DoaCrkuMaXc5211woY4Mvq25UZ7DUsx5o+mDoYoxU7HlgEB2QQnZZS7ExEsI+Ea11aTjrPJfkV7RkM9dUoiS7OkyS4PpCTV+S/vAA3bfkigWyF/FDDUBZiR2Gt39nbuotMvzFAGsDCS6pvrg/6Zkvnt4nO9ArQ0fYnTz7vtL5So2vE4NOwja4afvnn2Va+bubHDobufXFfpsHckyIO7JWHXMHULM5CGxSjV3ou4cgsSFzE/LovraK8IYamIysW51JApCvNGHXvPPO56CtpWFtMf/jQQ8qjB</publickey>
                  <signature>4114766194913785844307623478268920513207904809649390295191759339791248788857035079837285467140015294884268810863059294414714558478252286050429857099922149496212946962529416109370546760242342495327383015158042933406471591968103744617569754084992294893819302190358783127462323722586367855113145523366763033558219064643619554495523421005392982238445015008467696933018619012777969351010689810426614808111374535389775850513090968536153491255480569519856623066891877017655355744483137731360961139683030816198494031343962402377957266866817307216410794084720444986031021965708218747085220015804173278724096171222791791667812</signature>
                </identity>""",
            'fake_frank': """<?xml version="1.0" encoding="utf-8"?>
                <identity>
                  <sources>
                    <source>http://source_one_fake.com/frank.xml</source>
                    <source>http://source_two.net/frank.xml</source>
                  </sources>
                  <contacts>
                    <contact>tcp://:7592</contact>
                  </contacts>
                  <certificates/>
                  <scrubbers/>
                  <postage>1</postage>
                  <date>May 30, 2019</date>
                  <version></version>
                  <revision>0</revision>
                  <publickey>ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDIYCHrhzz0yPYfNMKFUSyb5LbtNoG0y9W2pHOhKPjXMsCe1nUYOHKmnRwLdhMzJ+4Mx1UCJmheHAiCvPDKZ7qRNL2X86eKNV9d0JHqW6xWiadteWHdzXHduVAWtOD1EIIxID3v5jprBN8oLDkTbgUrJutPOG+JuxyU5i9GXb5qhlmrM9ukNd4Hj7+prTjDeFIS7M/bJFNuYvLy0Yrc+pEOnGYquI6RvAkjm1uUJ00bsSd06PAUATRKtGVwpxG94puImi0WVgCt4GiGJg8t2Z6PRLbAx+XANmwxJ9tPe8CLeMgK8EXPKHjWcQCUd7OGBaPC0/EWAbGPBsEKdIpHB7gt</publickey>
                  <signature>16206868300008877600921412689140495979258182370971004976712222540672784322121155034535639220839641856686821577631474073534465139605541150548084768672667662041915184693218077142645108760479530793127888353599116529328440642295830641013482573397612652531617099990716006710125672240835999044307868547187943368721435308613499143472254021347039278129288941091656906768963279335231783540752918768035631991135921972481491603323358767582015322346254944209602633939214388411931371274962715907716821369696321108242409215811936218696777724808619934504255915444572390536771111074467526768287790568899120873106066002575368957232480</signature>
                </identity>""",
        }
        some_identity = identity.identity(xmlsrc=known.get(idname))
        self.assertTrue(some_identity.isCorrect())
        self.assertTrue(some_identity.Valid())
        id_url.identity_cached(some_identity)
        return some_identity

    def test_exceptions(self):
        with self.assertRaises(KeyError):
            id_url.field(alice_bin).to_public_key()
        with self.assertRaises(KeyError):
            (id_url.field(alice_bin) in {id_url.field(alice_bin): 'abc', })
        with self.assertRaises(KeyError):
            (alice_bin in {id_url.field(alice_bin): 'abc', })
        with self.assertRaises(KeyError):
            (id_url.field(alice_bin) == id_url.field(alice_bin))
        with self.assertRaises(KeyError):
            (id_url.field(alice_bin) == id_url.field(bob))
        with self.assertRaises(TypeError):
            (alice_bin in [id_url.field(alice_bin), ])
        with self.assertRaises(TypeError):
            (id_url.field(alice_text) == alice_bin)
        with self.assertRaises(TypeError):
            (id_url.field(alice_bin) == alice_text)
        with self.assertRaises(TypeError):
            (id_url.field(alice_bin) in [alice_bin, ])
        with self.assertRaises(TypeError):
            (id_url.field(alice_bin) not in [alice_bin, ])

    def test_identity_cached(self):
        alice_identity = self._cache_identity('alice')
        self.assertEqual(alice_identity.getIDURL().to_bin(), alice_bin)
        self.assertEqual(alice_identity.getIDURL().to_text(), alice_text)
        self.assertEqual(id_url.field(alice_bin).to_public_key(), alice_identity.getPublicKey())
        self.assertEqual(id_url.field(alice_text), id_url.field(alice_bin))
        self._cache_identity('bob')
        self.assertTrue(id_url.field(alice_text) != id_url.field(bob))
 
    def test_identity_not_cached(self):
        self._cache_identity('alice')
        with self.assertRaises(KeyError):
            (id_url.field(ethan_text) != id_url.field(alice_bin))
        l = [id_url.field(frank_2), ]
        with self.assertRaises(KeyError):
            (id_url.field(frank_1) not in l)
        self._cache_identity('frank')
        self.assertIn(id_url.field(frank_1), l)
   
    def test_empty(self):
        self.assertFalse(id_url.field(b''))
        self.assertFalse(id_url.field(''))
        self.assertFalse(id_url.field(None))
        self.assertFalse(id_url.field('None'))
        self.assertFalse(id_url.field(b'None'))
        self.assertTrue(bool(id_url.field(b'')) is False)
        self.assertTrue(bool(id_url.field('')) is False)
        self.assertTrue(bool(id_url.field(None)) is False)
        self.assertTrue(bool(id_url.field('None')) is False)
        self.assertTrue(bool(id_url.field(b'None')) is False)
        self.assertTrue(id_url.field(b'') is not None)
        self.assertTrue(id_url.field('') is not None)
        self.assertFalse(id_url.field(None) is None)
        self.assertTrue(id_url.field(None) is not None)
        with self.assertRaises(TypeError):
            (id_url.field(b'') == '')
        with self.assertRaises(TypeError):
            (id_url.field(b'') == b'')
        with self.assertRaises(TypeError):
            (id_url.field('') == '')
        with self.assertRaises(TypeError):
            (id_url.field('') == b'')
        with self.assertRaises(TypeError):
            (id_url.field(None) == '')
        with self.assertRaises(TypeError):
            (id_url.field(None) == b'')
        l = [b'', None, '', id_url.field(''), id_url.field(None), id_url.field(b''), ]
        self.assertIn(b'', l)
        self.assertIn('', l)
        self.assertIn(None, l)
        with self.assertRaises(TypeError):
            (None in [id_url.field(None), ])
        with self.assertRaises(TypeError):
            (None in [id_url.field(b''), ])
        with self.assertRaises(TypeError):
            (b'' in [id_url.field(None), ])
        with self.assertRaises(TypeError):
            (b'' in [id_url.field(b''), ])
        self.assertTrue(id_url.is_in(None, [id_url.field(None), ]))
        self.assertTrue(id_url.is_in(None, [id_url.field(b''), ]))
        self.assertTrue(id_url.is_in(b'', [id_url.field(None), ]))
        self.assertTrue(id_url.is_in(b'', [id_url.field(b''), ]))
        d = {id_url.field(''): 0, id_url.field(None): 1, id_url.field(b''): 2}
        with self.assertRaises(TypeError):
            (b'' in d)
        with self.assertRaises(TypeError):
            ('' in d)
        with self.assertRaises(TypeError):
            (b'' not in d)
        with self.assertRaises(TypeError):
            ('' not in d)
        self.assertNotIn(None, d)
        self.assertIn(id_url.field(''), d)
        self.assertIn(id_url.field(b''), d)
        self.assertIn(id_url.field(None), d)

    def test_not_empty(self):
        self.assertTrue(id_url.field(ethan_bin))
        self.assertTrue(id_url.field(ethan_text))
        self.assertTrue(bool(id_url.field(ethan_text)) is True)
        self.assertTrue(id_url.field(ethan_text).to_bin() != dave)

    def test_in_list(self):
        self._cache_identity('alice')
        self._cache_identity('bob')
        self._cache_identity('carl')
        l = [
            id_url.field(alice_text),
            id_url.field(bob),
            id_url.field(frank_1),
            id_url.field(frank_2),
        ]
        with self.assertRaises(KeyError):
            (id_url.field(carl) not in l)
        self.assertTrue(id_url.field(alice_text) in l)
        with self.assertRaises(KeyError):
            (id_url.field(b'http://fake.com/frank.xml') not in l)
        with self.assertRaises(KeyError):
            (id_url.field(ethan_not_exist) not in l)
        self.assertTrue(id_url.field(bob) in l)
        with self.assertRaises(KeyError):
            (id_url.field(frank_1) in l)
        with self.assertRaises(KeyError):
            (id_url.field(frank_2) in l)
        self.assertTrue(len(l), 4)
        with self.assertRaises(KeyError):
            (l[0] != l[3])
        with self.assertRaises(KeyError):
            (l[2] == l[3])
        self._cache_identity('frank')
        self.assertTrue(l[2] == l[3])
        self.assertTrue(l[0] != l[3])
        self.assertIn(id_url.field(frank_1), l)

    def test_idurl_in_dict(self):
        self._cache_identity('alice')
        self._cache_identity('bob')
        self._cache_identity('carl')
        d = {}
        d[id_url.field(alice_text)] = 'alice'
        d[id_url.field(bob)] = 'bob'
        self.assertIn(id_url.field(alice_text), d)
        self.assertNotIn(id_url.field(carl), d)
        self.assertTrue(id_url.is_in(alice_text, d))
        self.assertTrue(id_url.is_not_in(carl, d))

    def test_idurl_two_sources(self):
        with self.assertRaises(KeyError):
            {id_url.field(frank_1): 'frank1', }
        with self.assertRaises(KeyError):
            (id_url.field(frank_1) in {})
        with self.assertRaises(KeyError):
            (id_url.field(frank_2) in {})
        self._cache_identity('frank')
        d1 = {id_url.field(frank_1): 'frank1', }
        d2 = {id_url.field(frank_2): 'frank2', }
        self.assertEqual(id_url.field(frank_1), id_url.field(frank_2))
        self.assertIn(id_url.field(frank_1), d1)
        self.assertIn(id_url.field(frank_2), d2)
        self.assertIn(id_url.field(frank_1), d2)
        self.assertIn(id_url.field(frank_2), d1)
        self.assertTrue(id_url.is_in(frank_1, d2))
        self.assertTrue(id_url.is_in(frank_2, d2))
        self.assertEqual(list(d1.keys())[0], list(d2.keys())[0])
        self.assertEqual(list(d1.values())[0], 'frank1')
        self.assertEqual(d1.keys(), d2.keys())
        self.assertNotEqual(d1[id_url.field(frank_1)], d2[id_url.field(frank_2)])
        self.assertEqual(d1[id_url.field(frank_1)], d1[id_url.field(frank_2)])

    def test_idurl_three_sources(self):
        self._cache_identity('george')
        d3 = {
            id_url.field(george_1),
            id_url.field(george_2),
        }
        self.assertEqual(len(d3), 1)
        self.assertEqual(id_url.field(george_2), id_url.field(george_1))
        self.assertEqual(id_url.field(george_3), id_url.field(george_1))
        self.assertIn(id_url.field(george_1), d3)
        self.assertIn(id_url.field(george_2), d3)
        self.assertIn(id_url.field(george_3), d3)
        self._cache_identity('frank')
        self.assertNotIn(id_url.field(frank_1), d3)
        self.assertNotIn(id_url.field(frank_2), d3)
        self.assertFalse(id_url.is_in(frank_1, d3))
        self.assertTrue(id_url.is_in(george_1, d3))
        self.assertTrue(id_url.is_in(george_2, d3))
        self.assertTrue(id_url.is_in(george_3, d3))

    def test_fake_name(self):
        self._cache_identity('frank')
        self._cache_identity('fake_frank')
        self.assertEqual(id_url.field('http://source_one_fake.com/frank.xml'), id_url.field(frank_2))
        self.assertNotEqual(id_url.field('http://source_one_fake.com/frank.xml'), id_url.field(frank_1))
