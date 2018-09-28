from unittest import TestCase
import time

import subprocess


class Test(TestCase):

    def test_full_circle(self):
        t = time.time()

        dir_to_test = 'tests/data/test_%s' % t
        dir_to_files = 'tests/data/test_%s/bitdust' % t

        subprocess.call(['mkdir', dir_to_test])
        subprocess.call(['mkdir', dir_to_files])

        dir_to_origin_file = 'tests/data/1.jpg'
        dir_to_restored_file = '%s/restored_file.jpg' % dir_to_files

        subprocess.call(['cp', dir_to_origin_file, dir_to_files])

        subprocess.call(['python', 'raid/make.py', 'tests/data/1.jpg', 'ecc/4x4', 'myID_ABC', '100', dir_to_files])

        subprocess.call(['python', 'raid/read.py', dir_to_restored_file, 'ecc/4x4', 'bitdust', '100', 'tests/data/test_%s' % t])
        r = subprocess.call(['diff', dir_to_restored_file, dir_to_origin_file])
        self.assertEqual(r, 0, 'ERROR %s' % r)

        subprocess.call(['rm', '%s/100-0-Data' % dir_to_files])

        subprocess.call(['python', 'raid/read.py', dir_to_restored_file, 'ecc/4x4', 'bitdust', '100', 'tests/data/test_%s' % t])
        r = subprocess.call(['diff', dir_to_restored_file, dir_to_origin_file])
        self.assertEqual(r, 0, 'ERROR %s' % r)

        subprocess.call(['rm', '%s/100-1-Data' % dir_to_files])

        subprocess.call(['python', 'raid/read.py', dir_to_restored_file, 'ecc/4x4', 'bitdust', '100', 'tests/data/test_%s' % t])
        r = subprocess.call(['diff', dir_to_restored_file, dir_to_origin_file])
        self.assertEqual(r, 0, 'ERROR %s' % r)

        subprocess.call(['rm', '%s/100-2-Data' % dir_to_files])

        subprocess.call(['python', 'raid/read.py', dir_to_restored_file, 'ecc/4x4', 'bitdust', '100', 'tests/data/test_%s' % t])
        r = subprocess.call(['diff', dir_to_restored_file, dir_to_origin_file])
        self.assertEqual(r, 0, 'ERROR %s' % r)

        subprocess.call(['rm', '%s/100-3-Data' % dir_to_files])

        subprocess.call(['python', 'raid/read.py', dir_to_restored_file, 'ecc/4x4', 'bitdust', '100', 'tests/data/test_%s' % t])
        r = subprocess.call(['diff', dir_to_restored_file, dir_to_origin_file])
        self.assertEqual(r, 0, 'ERROR %s' % r)

        subprocess.call(['rm', '-rf', dir_to_test])
