from unittest import TestCase


_some_private_key = """-----BEGIN RSA PRIVATE KEY-----
MIICWwIBAAKBgQDP7lJ67hcSnWSFFzQs14brEBzovQfyoa7mkb+YkI9EJ/hEAsL7
xWCYk2erXNmY7WyeO7ABAJfp1Wg7/62XSl3f9J9ZeV71IPy32rWWNshfwDobcjlO
X+izEeq20Eac4p/lvuEbc1ACoSU2wvzfdEYn4Ol2KyrdbHWaZJInX0T4WwIDAQAB
An9U4HPKumWws47UxSQHKfNpAKrMVl1oLZe3hscu/9N7ftVY7cep/mfv4DvxN3Wb
d09fR/4Qaq2YRgTGeRfjKfgnNpBFtwSXGHIThNkN/H39N3w4IXFyZ2GemCsYIomm
MyW/i/ryh15hZyryCqBYLMVr6Yo5uml3n3cW4aeHwD9JAkEA2njymcj/5cpLETGV
VIGRgwzQbZDtRnya/0UTZD1hsh/KZizYZefWpHtiabGpztobpn4oMCvgqa9VKoGP
TORKAwJBAPOl0zSdyNuRi3773IsyCvilfPRWH1SjKA5EaRwYdWbkrKGjILvKYnDo
q2pEI8KJNWy7zyk0Zz1tjxhlU7XU9MkCQA/QgX8wVZXEtvpfpHehiW77FntX6lUX
4ABqd6Th7JiARJ5w0JlP1vHBHLaZ7bjTgPzkVPRnuLOPxZJ2HnFqdRECQQDfITPE
8eLqQeYQSrN0vkWR5GwEj4JtzmV2e2wPEM8jhbQa6vulPvjcEhg5X2GoXGOSyoQz
ZgxOEzGC0/jPgtERAkEA1KlbxGPkz7ZlRZ8jdNd9VnYG/LQlXwwsZ7c8fsnWhies
j1xY9wr6ou7N8kv4T8O5bnr5BNrvARPX/z4IdG4m+w==
-----END RSA PRIVATE KEY-----"""

class Test(TestCase):

    def test_sign_verify(self):
        import os
        import base64
        from logs import lg
        from crypt import my_keys
        lg.set_debug_level(30)
        key_id = 'test_key_01'
        my_keys.erase_key(key_id, keys_folder='/tmp/')
        # my_keys.generate_key(key_id, key_size=1024, keys_folder='/tmp/')
        my_keys.register_key(key_id, _some_private_key, keys_folder='/tmp/')
        self.assertTrue(my_keys.validate_key(my_keys.key_obj(key_id)))
        sample_data = b'12345678'  # base64.b64encode(os.urandom(100))
        raw_sign = my_keys.sign(key_id, inp=sample_data)
        is_valid = my_keys.verify(key_id, hashcode=sample_data, signature=raw_sign)
        # my_keys.erase_key(key_id, keys_folder='/tmp/')
        self.assertTrue(is_valid)
