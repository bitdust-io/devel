import os
import tempfile
import unittest
from unittest import TestCase

from bitdust.main import settings

from bitdust.system import bpio

from bitdust.logs import lg

from bitdust.lib import strng

from bitdust.userid import id_url
from bitdust.userid import identity

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
fake_frank = 'http://source_one_fake.com/frank.xml'
george_1 = 'http://source_one.com/george.xml'
george_2 = 'http://source_two.net/george.xml'
george_3 = 'http://source_3.org/george.xml'
hans1 = 'http://first.com/hans.xml'
hans2 = 'http://second.net/hans.xml'
hans3 = 'http://third.org/hans.xml'


class TestIDURL(TestCase):

    def setUp(self):
        try:
            bpio.rmdir_recursive('/tmp/.bitdust_tmp')
        except Exception:
            pass
        lg.set_debug_level(30)
        settings.init(base_dir='/tmp/.bitdust_tmp')
        id_url._IdentityHistoryDir = tempfile.mkdtemp()
        id_url.init()
        try:
            os.makedirs('/tmp/.bitdust_tmp/identitycache/')
        except:
            pass
        try:
            os.makedirs('/tmp/.bitdust_tmp/identityhistory/')
        except:
            pass

    def tearDown(self):
        id_url.shutdown()
        settings.shutdown()
        bpio.rmdir_recursive('/tmp/.bitdust_tmp')

    def _cache_identity(self, idname='alice'):
        known = {
            'alice':
            """<?xml version="1.0" encoding="utf-8"?>
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
            'bob':
            """<?xml version="1.0" encoding="utf-8"?>
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
            'carl':
            """<?xml version="1.0" encoding="utf-8"?>
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
            'frank':
            """<?xml version="1.0" encoding="utf-8"?>
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
            'george':
            """<?xml version="1.0" encoding="utf-8"?>
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
            'fake_frank':
            """<?xml version="1.0" encoding="utf-8"?>
                <identity>
                  <sources>
                    <source>http://source_one_fake.com/frank.xml</source>
                    <source>http://source_two.net/frank.xml</source>
                  </sources>
                  <contacts>
                    <contact>tcp://127.0.0.1:7169</contact>
                  </contacts>
                  <certificates/>
                  <scrubbers/>
                  <postage>1</postage>
                  <date>Jul 01, 2019</date>
                  <version></version>
                  <revision>0</revision>
                  <publickey>ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCS5wf0kaJa7zLwYWBEj+/JzfMhxFcMUy6Fz6DcuFCK05i1VgeFHuEEbpkU4yAYiNX1YGb4FBOfJ95UFM8HOB6b8QDqA6uHOkjT/aNiaL7fj+LG7UwqGef5cEWbckIpaeZQiyWaNuTtp2rywPrEakIs7KUFcdtiPhvtjymT8PyFRhSOoRO2U9+54K+FFJH9XQtSPB+KNdNOm18tFPJ4lviEODCKH0rE9BQ4Vn/auO0KBcwX8AGuhUFI0nsaQtHcty1L6u1UXHrEXGZeu2yBhEsHDHunxW+h0YOgCRdI8Usnobdx/dyJ7momABnu6mElt/ylHzM98nM/NfmM5BOrG9Tv</publickey>
                  <signature>13107260235651409913492390604656826449101578484743079806566807521296855989324803242511319779707838174946127035306858215504290452087950300644093221553306839853186323155012108941951146067164825000001482898225482538135328083540275907917650591073062847715060678819674667948896781152495669494916549386439852946976965970389941158492538138518594892617227070532550696583600653695158346473408694303871305287828335597832662071836974941142069312163761621166361732834315345454522029016656941848429213536700288288831888079827237495251089188669161987255910430438434187684912979732275126065406389681858156899388574380125659081087827</signature>
                </identity>""",
            'hans1':
            """<?xml version="1.0" encoding="utf-8"?>
                <identity>
                  <sources>
                    <source>http://first.com/hans.xml</source>
                    <source>http://second.net/hans.xml</source>
                  </sources>
                  <contacts>
                    <contact>tcp://127.0.0.1:7457</contact>
                  </contacts>
                  <certificates/>
                  <scrubbers/>
                  <postage>1</postage>
                  <date>Jul 01, 2019</date>
                  <version></version>
                  <revision>0</revision>
                  <publickey>ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCiMX5AjFoK+B8bEts97OEKkJmONy8wDVSTe4Sx356p1fd48UQHq0g3xphfEWqZNVEvvXyVT3ToJZpsn6ZXALR6awp1EosV0Y3eCRn3HJ7VFifsObEBaJlbIpPWO3a44yQuNmB18dpAZsOYF0fuv9O9JZF/r2aS3DwJKKvrb1raPtuOkmLvMFOyFzQ4CzbpzOhxfLyk4VyyqWtxgRWa3cLJRC1s8pZP+Eeujz9lUXJOBJkz458myjcNogZ60HqMWPmNEQxKQKxKz5s1KhTzEa13AbK3mfBz6GYRSUE4PgzPNGt3ggKjm109MCECVLJ20i41l1x0LQogH4io0zN1KGFJ</publickey>
                  <signature>13068553383637753085388545974152093609980484012770452572120600195304903547295645115743544723314736720580808645983593697230309177682054712275065288665744892926477896400614384619512508972942866186572904043048207845632626832350683561290105271937200406689170558357079802162498698787054408426873656285478048378799191423141745937328344899208835186975874729426520455853791306586430419171014111851754881354985456443997095404651969419163775186405638979606072817375092764901667492456855939205354792829575562245938026302306124652445463109637611383925691836897970969979043999831425972117577943735372131767450971245110225874441582</signature>
                </identity>""",
            'hans2':
            """<?xml version="1.0" encoding="utf-8"?>
                <identity>
                  <sources>
                    <source>http://second.net/hans.xml</source>
                    <source>http://third.org/hans.xml</source>
                  </sources>
                  <contacts>
                    <contact>tcp://127.0.0.1:7457</contact>
                  </contacts>
                  <certificates/>
                  <scrubbers/>
                  <postage>1</postage>
                  <date>Jul 01, 2019</date>
                  <version></version>
                  <revision>1</revision>
                  <publickey>ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCiMX5AjFoK+B8bEts97OEKkJmONy8wDVSTe4Sx356p1fd48UQHq0g3xphfEWqZNVEvvXyVT3ToJZpsn6ZXALR6awp1EosV0Y3eCRn3HJ7VFifsObEBaJlbIpPWO3a44yQuNmB18dpAZsOYF0fuv9O9JZF/r2aS3DwJKKvrb1raPtuOkmLvMFOyFzQ4CzbpzOhxfLyk4VyyqWtxgRWa3cLJRC1s8pZP+Eeujz9lUXJOBJkz458myjcNogZ60HqMWPmNEQxKQKxKz5s1KhTzEa13AbK3mfBz6GYRSUE4PgzPNGt3ggKjm109MCECVLJ20i41l1x0LQogH4io0zN1KGFJ</publickey>
                  <signature>9964338615595898119523219160985389694716834455244251121310208348749311239026480163448985744966067564091031002898262983039746088711129723160991957466541609144298294968214985017280673670405176798626865604720543551314153138295619813468551357860935622955238006750497782286078815952649485259190562480676412057686853832517927221963473242813486514373660489478033158129265672776156687967394550999847921296632829991543789469343181140623972591265599094214576144469741220772769413300453153162888368211327094417654762184709016011327148922218562411856167502006839171679742071717903072564535777785105712764567873880374805969385183</signature>
                </identity>""",
            'hans3':
            """<?xml version="1.0" encoding="utf-8"?>
                <identity>
                  <sources>
                    <source>http://third.org/hans.xml</source>
                  </sources>
                  <contacts>
                    <contact>tcp://127.0.0.1:7457</contact>
                  </contacts>
                  <certificates/>
                  <scrubbers/>
                  <postage>1</postage>
                  <date>Jul 01, 2019</date>
                  <version></version>
                  <revision>2</revision>
                  <publickey>ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCiMX5AjFoK+B8bEts97OEKkJmONy8wDVSTe4Sx356p1fd48UQHq0g3xphfEWqZNVEvvXyVT3ToJZpsn6ZXALR6awp1EosV0Y3eCRn3HJ7VFifsObEBaJlbIpPWO3a44yQuNmB18dpAZsOYF0fuv9O9JZF/r2aS3DwJKKvrb1raPtuOkmLvMFOyFzQ4CzbpzOhxfLyk4VyyqWtxgRWa3cLJRC1s8pZP+Eeujz9lUXJOBJkz458myjcNogZ60HqMWPmNEQxKQKxKz5s1KhTzEa13AbK3mfBz6GYRSUE4PgzPNGt3ggKjm109MCECVLJ20i41l1x0LQogH4io0zN1KGFJ</publickey>
                  <signature>11958004301656338144383334445736600827209441963611815598420603918822211142526966075720891212808194909550288382243052852622156637099050410373511336910133303791008042473718309984723895304895629463705900053550743363551114431658248065643054664707971189331530190824121429353343469077985523096241437248019113197103461636847516945163199302563987603148811708018950051799390582546914509552932256650563055856190431745640579914653327517317125317899208768049182599520431852111466415308484761163553541804212696743391960660588998008501810208556514930557535867983962893715967502497080388797303899102334976976072133672653305360264021</signature>
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
            (id_url.field(alice_bin) in {
                id_url.field(alice_bin): 'abc',
            })
        with self.assertRaises(KeyError):
            (alice_bin in {
                id_url.field(alice_bin): 'abc',
            })
        with self.assertRaises(KeyError):
            (id_url.field(alice_bin) == id_url.field(alice_bin))
        with self.assertRaises(KeyError):
            (id_url.field(alice_bin) == id_url.field(bob))
        with self.assertRaises(TypeError):
            (alice_bin in [
                id_url.field(alice_bin),
            ])
        with self.assertRaises(TypeError):
            (id_url.field(alice_text) == alice_bin)
        with self.assertRaises(TypeError):
            (id_url.field(alice_bin) == alice_text)
        with self.assertRaises(TypeError):
            (id_url.field(alice_bin) in [
                alice_bin,
            ])
        with self.assertRaises(TypeError):
            (id_url.field(alice_bin) not in [
                alice_bin,
            ])

    def test_identity_cached(self):
        self.assertFalse(id_url.is_cached(alice_bin))
        self.assertFalse(id_url.is_cached(alice_text))
        alice_identity = self._cache_identity('alice')
        self.assertTrue(id_url.is_cached(alice_bin))
        self.assertTrue(id_url.is_cached(alice_text))
        self.assertEqual(alice_identity.getIDURL().to_bin(), alice_bin)
        self.assertEqual(alice_identity.getIDURL().to_text(), alice_text)
        self.assertEqual(id_url.field(alice_bin).to_public_key(), alice_identity.getPublicKey())
        self.assertEqual(id_url.field(alice_text), id_url.field(alice_bin))
        self._cache_identity('bob')
        self.assertTrue(id_url.field(alice_text) != id_url.field(bob))
        self.assertEqual(str(id_url.field(alice_text)), 'http://127.0.0.1:8084/alice.xml')
        self.assertEqual(repr(id_url.field(alice_text)), '{http://127.0.0.1:8084/alice.xml}')
        self.assertEqual('=%s=' % id_url.field(alice_text), '=http://127.0.0.1:8084/alice.xml=')
        self.assertEqual('=%r=' % id_url.field(alice_text), '={http://127.0.0.1:8084/alice.xml}=')
        self.assertEqual(id_url.field(alice_text).unique_name(), 'alice_1c32a98ab413b6a2deb6a7f38f8b56fffc4e983f')
        self.assertIn(alice_bin, id_url.sources(id_url.field(alice_text).to_public_key()))
        self.assertIn(alice_bin, id_url.unique_names(id_url.field(alice_text).unique_name()))

    def test_identity_not_cached(self):
        self._cache_identity('alice')
        with self.assertRaises(KeyError):
            (id_url.field(ethan_text) != id_url.field(alice_bin))
        l = [
            id_url.field(frank_2),
        ]
        with self.assertRaises(KeyError):
            (id_url.field(frank_1) not in l)
        self._cache_identity('frank')
        self.assertIn(id_url.field(frank_1), l)

    def test_empty(self):
        self.assertTrue(id_url.is_empty(id_url.field(b'')))
        self.assertTrue(id_url.is_empty(id_url.field('')))
        self.assertTrue(id_url.is_empty(id_url.field(None)))
        self.assertTrue(id_url.is_empty(id_url.field(b'None')))
        self.assertTrue(id_url.is_empty(None))
        self.assertTrue(id_url.is_empty(b''))
        self.assertTrue(id_url.is_empty(''))
        self.assertTrue(id_url.is_empty(b'None'))
        self.assertTrue(id_url.is_empty('None'))
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
        self.assertTrue(id_url.field(b'') == b'')
        self.assertTrue(id_url.field('') == '')
        self.assertTrue(id_url.field('') == b'')
        self.assertTrue(id_url.field(None) == '')
        self.assertTrue(id_url.field(None) == b'')
        l = [
            b'',
            None,
            '',
            id_url.field(''),
            id_url.field(None),
            id_url.field(b''),
        ]
        self.assertIn(b'', l)
        self.assertIn('', l)
        self.assertIn(None, l)
        self.assertTrue(id_url.is_some_empty(l))
        self.assertEqual(l.count(None), 4)
        self.assertEqual(id_url.empty_count(l), 6)
        self.assertTrue(
            None in [
                id_url.field(None),
            ],
        )
        self.assertTrue(
            None in [
                id_url.field(b''),
            ],
        )
        self.assertTrue(
            b'' in [
                id_url.field(None),
            ],
        )
        self.assertTrue(
            b'' in [
                id_url.field(b''),
            ],
        )
        self.assertTrue(
            id_url.is_in(
                None,
                [
                    id_url.field(None),
                ],
            )
        )
        self.assertTrue(
            id_url.is_in(
                None,
                [
                    id_url.field(b''),
                ],
            )
        )
        self.assertTrue(
            id_url.is_in(
                b'',
                [
                    id_url.field(None),
                ],
            )
        )
        self.assertTrue(
            id_url.is_in(
                b'',
                [
                    id_url.field(b''),
                ],
            )
        )
        d = {id_url.field(''): 0, id_url.field(None): 1, id_url.field(b''): 2}
        self.assertTrue(len(d), 1)
        self.assertTrue(b'' in d)
        self.assertTrue('' in d)
        self.assertFalse(b'' not in d)
        self.assertFalse('' not in d)
        self.assertNotIn(None, d)
        self.assertIn(id_url.field(''), d)
        self.assertIn(id_url.field(b''), d)
        self.assertIn(id_url.field(None), d)

    def test_not_empty(self):
        self.assertFalse(id_url.is_empty(id_url.field(ethan_bin)))
        self.assertFalse(id_url.is_empty(id_url.field(ethan_text)))
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
        self.assertFalse(id_url.is_some_empty(l))
        self.assertEqual(l.count(None), 0)
        self.assertEqual(id_url.empty_count(l), 0)
        l += [
            id_url.field(b''),
        ] * 3
        self.assertEqual(l.count(None), 3)
        self.assertEqual(l.count(b''), 3)
        self.assertEqual(l.count(''), 3)
        self.assertEqual(l.count(id_url.field(None)), 3)
        self.assertEqual(l.count(id_url.field(b'')), 3)
        self.assertEqual(l.count(id_url.field('')), 3)
        self.assertEqual(
            id_url.fields_list([
                b'',
            ]),
            [
                b'',
            ],
        )
        self.assertEqual(
            id_url.fields_list([
                b'',
            ]),
            [
                None,
            ],
        )
        self.assertEqual(
            id_url.fields_list([
                id_url.field(''),
            ]),
            [
                None,
            ],
        )
        self.assertEqual(
            id_url.fields_list([
                None,
            ]),
            [
                id_url.field(''),
            ],
        )
        self.assertNotEqual(
            id_url.fields_list([None, None]),
            [
                id_url.field(''),
            ],
        )
        self.assertEqual(
            len(
                id_url.fields_list([
                    None,
                ]),
            ),
            1,
        )

    def test_in_dict(self):
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
        d2 = {
            id_url.field(bob): 'bob',
            'some_key': 'some_value',
        }
        self.assertIn('some_key', d2)
        keys = list(d2.keys())
        with self.assertRaises(TypeError):
            (keys[0] != keys[1])

    def test_dict_of_lists(self):
        self._cache_identity('alice')
        self._cache_identity('bob')
        self._cache_identity('carl')
        self._cache_identity('frank')
        d = {}
        d[id_url.field(alice_text)] = []
        d[id_url.field(bob)] = []
        d[id_url.field(alice_text)].append(id_url.field(carl))
        d[id_url.field(alice_text)].append(id_url.field(frank_1))
        d[id_url.field(bob)].append(id_url.field(''))
        d[id_url.field(bob)].append(id_url.field(frank_2))
        d[id_url.field(bob)].append(id_url.field(None))
        d[id_url.field(bob)].append(id_url.field(b''))
        self.assertIn(id_url.field(frank_1), d[id_url.field(alice_text)])
        self.assertIn(id_url.field(frank_1), d[id_url.field(bob)])
        self.assertFalse(id_url.is_some_empty(d[id_url.field(alice_text)]))
        self.assertTrue(id_url.is_some_empty(d[id_url.field(bob)]))
        self.assertEqual(len(id_url.fields_list(d[id_url.field(bob)])), 4)

    def test_two_sources(self):
        with self.assertRaises(KeyError):
            {
                id_url.field(frank_1): 'frank1',
            }
        with self.assertRaises(KeyError):
            (id_url.field(frank_1) in {})
        with self.assertRaises(KeyError):
            (id_url.field(frank_2) in {})
        self._cache_identity('frank')
        d1 = {
            id_url.field(frank_1): 'frank1',
        }
        d2 = {
            id_url.field(frank_2): 'frank2',
        }
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

    def test_three_sources(self):
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
        self.assertNotEqual(id_url.field(fake_frank).original(), id_url.field(frank_1).original())
        self.assertNotEqual(id_url.field(fake_frank).original(), id_url.field(frank_2).original())
        self.assertNotEqual(id_url.field(fake_frank), id_url.field(frank_1))
        self.assertEqual(id_url.field(fake_frank), id_url.field(frank_2))
        self.assertNotEqual(id_url.field(fake_frank).to_public_key(), id_url.field(frank_1).to_public_key())
        self.assertEqual(id_url.field(fake_frank).to_public_key(), id_url.field(frank_2).to_public_key())

    def test_latest_vs_original(self):
        idurl_hans_not_cached = id_url.field(hans1)
        self.assertEqual('=%r=' % idurl_hans_not_cached, '={http://first.com/hans.xml}=')
        self._cache_identity('hans1')
        idurl_hans_cached = id_url.field(hans1)
        self.assertEqual('=%r=' % idurl_hans_cached, '={http://first.com/hans.xml}=')
        self.assertEqual('=%r=' % id_url.field(hans1), '={http://first.com/hans.xml}=')
        self._cache_identity('hans2')
        self.assertEqual('=%r=' % id_url.field(hans1), '={*http://second.net/hans.xml}=')
        self._cache_identity('hans3')
        self.assertEqual('=%r=' % id_url.field(hans1), '={*http://third.org/hans.xml}=')
        self.assertEqual(id_url.field(hans1), id_url.field(hans2))
        self.assertNotEqual(id_url.field(hans1).original(), id_url.field(hans2).original())
        self.assertEqual(id_url.field(hans1), id_url.field(hans3))
        self.assertNotEqual(id_url.field(hans1).original(), id_url.field(hans3).original())
        self.assertEqual(id_url.field(hans3), id_url.field(hans2))
        self.assertNotEqual(id_url.field(hans3).original(), id_url.field(hans2).original())
        self.assertEqual(id_url.field(hans1).to_text(), hans3)
        self.assertEqual(id_url.field(hans2).to_text(), hans3)
        self.assertEqual(id_url.field(hans3).to_text(), hans3)
        idurl_hans1 = id_url.field(hans1)
        self.assertEqual('=%r=' % idurl_hans1, '={*http://third.org/hans.xml}=')
        self.assertFalse(idurl_hans1.refresh())
        self.assertEqual('=%r=' % idurl_hans1, '={*http://third.org/hans.xml}=')
        idurl_hans2 = id_url.field(hans2)
        self.assertEqual('=%r=' % idurl_hans2, '={*http://third.org/hans.xml}=')
        self.assertFalse(idurl_hans2.refresh())
        self.assertEqual('=%r=' % idurl_hans2, '={*http://third.org/hans.xml}=')
        idurl_hans3 = id_url.field(hans3)
        self.assertEqual('=%r=' % idurl_hans3, '={http://third.org/hans.xml}=')
        self.assertFalse(idurl_hans3.refresh())
        self.assertEqual('=%r=' % idurl_hans3, '={http://third.org/hans.xml}=')
        self.assertTrue(idurl_hans_not_cached.refresh())
        self.assertEqual('=%r=' % idurl_hans_not_cached, '={http://third.org/hans.xml}=')
        self.assertTrue(idurl_hans_cached.refresh())
        self.assertEqual('=%r=' % idurl_hans_cached, '={http://third.org/hans.xml}=')

    def test_latest_revision_order_123(self):
        self._cache_identity('hans1')
        self._cache_identity('hans2')
        self._cache_identity('hans3')
        self.assertNotEqual(id_url.field(hans1).to_text(), hans1)
        self.assertNotEqual(id_url.field(hans2).to_text(), hans1)
        self.assertNotEqual(id_url.field(hans3).to_text(), hans1)
        self.assertNotEqual(id_url.field(hans1).to_text(), hans2)
        self.assertNotEqual(id_url.field(hans2).to_text(), hans2)
        self.assertNotEqual(id_url.field(hans3).to_text(), hans2)
        self.assertEqual(id_url.field(hans1).to_text(), hans3)
        self.assertEqual(id_url.field(hans2).to_text(), hans3)
        self.assertEqual(id_url.field(hans3).to_text(), hans3)
        self.assertEqual(id_url.field(hans1).original(), strng.to_bin(hans1))
        self.assertEqual(id_url.field(hans2).original(), strng.to_bin(hans2))
        self.assertEqual(id_url.field(hans3).original(), strng.to_bin(hans3))

    def test_latest_revision_order_321(self):
        self._cache_identity('hans3')
        self._cache_identity('hans2')
        self._cache_identity('hans1')
        self.assertNotEqual(id_url.field(hans1).to_text(), hans1)
        self.assertNotEqual(id_url.field(hans2).to_text(), hans1)
        self.assertNotEqual(id_url.field(hans3).to_text(), hans1)
        self.assertNotEqual(id_url.field(hans1).to_text(), hans2)
        self.assertNotEqual(id_url.field(hans2).to_text(), hans2)
        self.assertNotEqual(id_url.field(hans3).to_text(), hans2)
        self.assertEqual(id_url.field(hans1).to_text(), hans3)
        self.assertEqual(id_url.field(hans2).to_text(), hans3)
        self.assertEqual(id_url.field(hans3).to_text(), hans3)
        self.assertEqual(id_url.field(hans1).original(), strng.to_bin(hans1))
        self.assertEqual(id_url.field(hans2).original(), strng.to_bin(hans2))
        self.assertEqual(id_url.field(hans3).original(), strng.to_bin(hans3))


if __name__ == '__main__':
    unittest.main()
