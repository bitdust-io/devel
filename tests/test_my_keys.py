from unittest import TestCase


class Test(TestCase):

    def test_sign_verify(self):
        import os
        import base64
        from crypt import my_keys
        key_id = 'test_key_01'
        my_keys.erase_key(key_id, keys_folder='/tmp/')
        my_keys.generate_key(key_id, key_size=1024, keys_folder='/tmp/')
        my_keys.validate_key(my_keys.key_obj(key_id))
        sample_data = base64.b64encode(os.urandom(100))
        raw_sign = my_keys.sign(key_id, inp=sample_data)
        is_valid = my_keys.verify(key_id, hashcode=sample_data, signature=raw_sign)
        my_keys.erase_key(key_id, keys_folder='/tmp/')
        self.assertTrue(is_valid)
