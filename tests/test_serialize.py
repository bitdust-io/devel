from unittest import TestCase


class Test(TestCase):

    def test_jsn(self):
        import os
        from lib import jsn
        data1 = os.urandom(1024)
        dct1 = {'d': {'data': data1, }, }
        raw = jsn.dumps(dct1, encoding='latin1')
        dct2 = jsn.loads(raw, encoding='latin1')
        data2 = dct2['d']['data']
        self.assertEqual(data1, data2)

    def test_serialization(self):
        import os
        from lib import serialization
        data1 = os.urandom(1024)
        dct1 = {'d': {'data': data1, }, }
        raw = serialization.DictToBytes(dct1)
        dct2 = serialization.BytesToDict(raw)
        data2 = dct2['d']['data']
        self.assertEqual(data1, data2)

    def test_signed_packet(self):
        import os
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
        src1 = p1.Serialize()

        p2 = signed.Unserialize(src1)
        src2 = p2.Serialize()
        data2 = p2.Payload
        self.assertEqual(data1, data2)
        self.assertEqual(src1, src2)

        p3 = signed.Unserialize(src2)
        src3 = p3.Serialize()
        data3 = p3.Payload
        self.assertEqual(data1, data3)
        self.assertEqual(src1, src3)
