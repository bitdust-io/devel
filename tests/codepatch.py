import os
import sys

for filename in os.listdir(sys.argv[1]):
    path = os.path.join(sys.argv[1], filename)
    if not filename.endswith('.py'):
        continue
    src = open(path).read()
    newsrc = ''
    lines = src.splitlines()

    for line in lines:
        words = line.split(' ')
        # if line.startswith('from lib import'):
        #     modul = words[3].strip()
        #     line = 'import lib.%s as %s' % (modul, modul)
        # if len(words)==4 and words[0] == 'from' and words[2]=='import':
        #     if words[1] in ['lib', 'userid', 'transport', 'stun', 'dht']:
        #         line = 'import %s.%s as %s' % (words[1], words[3], words[3])
        # line = line.replace('from lib import dhnio', 'import lib.dhnio as dhnio')
        if len(words) == 4:
            if words[0] == 'import' and words[2] == 'as':
                pkg, modl = words[1].split('.')
                if modl == words[3]:
                    print path, line
                    line = 'from %s import %s' % (pkg, modl) 
        newsrc += line + '\n'

    
#    doclines = False
#    for line in lines:
#        if line.strip() == '"""':
#            if not doclines:
#                doclines = True
#            else:
#                doclines = False
#            newsrc += line+'\n'
#        else:
#            if doclines:
#                newsrc += line.replace('`', '``')+'\n'
#            else: 
#                newsrc += line+'\n'
#    newsrc = newsrc.replace('``', '``')
    
    # lines = src.splitlines()
    # first_docstring_pos = False
    # for line in lines:
    #     newsrc += line+'\n'
    #     if line.startswith('"""') and first_docstring_pos is False:
    #         first_docstring_pos = True
    #         newsrc += '.. module:: %s\n\n' % (filename[:-3])
    #         continue
    
    open(path, 'w').write(newsrc)
