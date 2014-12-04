import sys
import re
md_base = '../'
gitlab_base = 'http://gitlab.bitpie.net/devel/bitpie.devel/blob/master/'
template = open('html.template').read()
src = sys.argv[1]
dest = sys.argv[2]
sbody = open(src).read()
sbody = re.sub('a href="(.+?)\.md"', 'a href="%s\g<1>.html"' % md_base, sbody)
sbody = re.sub('a href="(.+?)\.py"', 'a href="%s\g<1>.py"' % gitlab_base, sbody)
sbody = re.sub('\<p\>\<img alt="', '<p><img width=1000 alt="', sbody) 
newbody = template % {
	'title': src.replace('.html', ''),
	'body': sbody}
open(dest, mode='w').write(newbody)