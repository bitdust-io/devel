from distutils.core import setup
import py2exe, sys, os

sys.argv.append('py2exe')

setup(
    options = { 'py2exe': { 'includes': ["pp.ppworker"] } },
    console = ["sum_primes.py"],
    data_files = [ ('',[r'C:\Python25\python.exe']) ],
)

# We need to add the source code of the function into the library.zip modules
from zipfile import ZipFile
zip = ZipFile('dist/library.zip','a')
zip.write("primes.py")
