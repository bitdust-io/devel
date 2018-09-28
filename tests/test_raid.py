from unittest import TestCase
import time

import subprocess


class Test(TestCase):

    def setUp(self):
        t = time.time()

        self.dir_to_test = 'tests/data/test_%s' % t
        self.dir_to_files = 'tests/data/test_%s/bitdust' % t

        subprocess.call(['mkdir', self.dir_to_test])
        subprocess.call(['mkdir', self.dir_to_files])

        self.dir_to_origin_file = 'tests/data/1.jpg'
        self.dir_to_restored_file = '%s/restored_file.jpg' % self.dir_to_files

        subprocess.call(['cp', self.dir_to_origin_file, self.dir_to_files])

    def tearDown(self):
        subprocess.call(['rm', '-rf', self.dir_to_test])

    def test_full_circle(self):
        dir_to_test = self.dir_to_test
        dir_to_files = self.dir_to_files
        dir_to_origin_file = self.dir_to_origin_file
        dir_to_restored_file = self.dir_to_restored_file

        subprocess.call(['python', 'raid/make.py', 'tests/data/1.jpg', 'ecc/4x4', 'myID_ABC', '100', dir_to_files])

        subprocess.call(['python', 'raid/read.py', dir_to_restored_file, 'ecc/4x4', 'bitdust', '100', dir_to_test])
        r = subprocess.call(['diff', dir_to_restored_file, dir_to_origin_file])
        self.assertEqual(r, 0, 'ERROR %s' % r)

        subprocess.call(['rm', '%s/100-0-Data' % dir_to_files])

        subprocess.call(['python', 'raid/read.py', dir_to_restored_file, 'ecc/4x4', 'bitdust', '100', dir_to_test])
        r = subprocess.call(['diff', dir_to_restored_file, dir_to_origin_file])
        self.assertEqual(r, 0, 'ERROR %s' % r)

        subprocess.call(['rm', '%s/100-1-Data' % dir_to_files])

        subprocess.call(['python', 'raid/read.py', dir_to_restored_file, 'ecc/4x4', 'bitdust', '100', dir_to_test])
        r = subprocess.call(['diff', dir_to_restored_file, dir_to_origin_file])
        self.assertEqual(r, 0, 'ERROR %s' % r)

        subprocess.call(['rm', '%s/100-2-Data' % dir_to_files])

        subprocess.call(['python', 'raid/read.py', dir_to_restored_file, 'ecc/4x4', 'bitdust', '100', dir_to_test])
        r = subprocess.call(['diff', dir_to_restored_file, dir_to_origin_file])
        self.assertEqual(r, 0, 'ERROR %s' % r)

        subprocess.call(['rm', '%s/100-3-Data' % dir_to_files])

        subprocess.call(['python', 'raid/read.py', dir_to_restored_file, 'ecc/4x4', 'bitdust', '100', dir_to_test])
        r = subprocess.call(['diff', dir_to_restored_file, dir_to_origin_file])
        self.assertEqual(r, 0, 'ERROR %s' % r)

        subprocess.call(['rm', '-rf', dir_to_test])
