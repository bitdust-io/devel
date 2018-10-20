from unittest import TestCase
import os


class Test(TestCase):

    def test_jsn(self):
        from lib import jsn
        data1 = os.urandom(1024)
        dct1 = {'d': {'data': data1, }, }
        raw = jsn.dumps(dct1, encoding='latin1')
        dct2 = jsn.loads(raw, encoding='latin1')
        data2 = dct2['d']['data']
        self.assertEqual(data1, data2)

    def test_serialization(self):
        from lib import serialization
        data1 = os.urandom(1024)
        dct1 = {'d': {'data': data1, }, }
        raw = serialization.DictToBytes(dct1)
        dct2 = serialization.BytesToDict(raw)
        data2 = dct2['d']['data']
        self.assertEqual(data1, data2)

    def test_signed_packet(self):
        from crypt import key
        from crypt import signed
        from userid import my_id

        key.InitMyKey()
        data1 = os.urandom(1024)
        p1 = signed.Packet(
            'Data',
            my_id.getLocalID(),
            my_id.getLocalID(),
            'SomeID',
            data1,
            'RemoteID:abc',
        )
        self.assertTrue(p1.Valid())
        raw1 = p1.Serialize()

        p2 = signed.Unserialize(raw1)
        self.assertTrue(p2.Valid())
        raw2 = p2.Serialize()
        data2 = p2.Payload
        self.assertEqual(data1, data2)
        self.assertEqual(raw1, raw2)

    def test_encrypted_block(self):
        from crypt import key
        from crypt import encrypted
        from userid import my_id

        key.InitMyKey()
        data1 = os.urandom(1024)
        b1 = encrypted.Block(
            CreatorID=my_id.getLocalIDURL(),
            BackupID='BackupABC',
            BlockNumber=123,
            SessionKey=key.NewSessionKey(),
            SessionKeyType=key.SessionKeyType(),
            LastBlock=True,
            Data=data1,
        )
        self.assertTrue(b1.Valid())
        raw1 = b1.Serialize()

        b2 = encrypted.Unserialize(raw1)
        self.assertTrue(b2.Valid())
        raw2 = b2.Serialize()
        data2 = b2.Data()
        self.assertEqual(data1, data2)
        self.assertEqual(raw1, raw2)
