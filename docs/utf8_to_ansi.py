import sys
import codecs
import locale
src = codecs.open(sys.argv[1], mode='r').read().decode('utf8')
src = src.encode(locale.getpreferredencoding())
codecs.open(sys.argv[2], mode='w').write(src)