import os
import sys
import io 
import codecs
import locale
import re

md_base = '../'
gitlab_base = 'http://gitlab.bitpie.net/devel/bitpie.devel/blob/master/'
template = open('html.template').read()
subdir = sys.argv[1]
dirpath = '../' + subdir

if not os.path.isdir(subdir):
    os.mkdir(subdir)
    
os.system('del /Q %s\\*' % subdir)

for fn in os.listdir(dirpath):
    if not fn.endswith('.md'):
        continue
    fp = os.path.join(dirpath, fn)
    print fp
    try:
        fphtml = os.path.join(subdir, fn[:-3] + '.html')
        r = os.system('python -m markdown %s > %s' % (fp, fphtml))
        if r != 0:
            break
        shtml = codecs.open(fphtml, mode='r').read().decode('utf8')
        sbody = shtml.encode(locale.getpreferredencoding())
        sbody = re.sub('href="(.+?)\.md"', 'href="%s\g<1>.html"' % md_base, sbody)
        sbody = re.sub('href="(.+?)\.py"', 'href="%s\g<1>.py"' % gitlab_base, sbody)
        sbody = re.sub('\<p\>\<img alt="', '<p><img width=1000 alt="', sbody) 
        dest = template % {
            'title': fn.replace('.md', ''),
            'body': sbody}
        codecs.open(fphtml, mode='w').write(dest)
    except:
        import traceback
        traceback.print_exc()
        break
    
    
    
    