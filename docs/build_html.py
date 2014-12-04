import os
import sys

subdir = sys.argv[1]
dirpath = '../' + subdir

if not os.path.isdir(subdir):
    os.mkdir(subdir)

if subdir != '.':
    os.system('del /Q %s\\*' % subdir)

for fn in os.listdir(dirpath):
    if not fn.endswith('.md'):
        continue
    fp = os.path.join(dirpath, fn)
    fphtml = os.path.join(subdir, fn[:-3] + '.html')
    print fp, '->', fphtml
    try:
        r = os.system('python -m markdown %s > %s' % (fp, fphtml))
        if r != 0:
            break
        r = os.system('python utf8_to_ansi.py %s %s' % (fphtml, fphtml))
        if r != 0:
            break
        r = os.system('python fix_html.py %s %s' % (fphtml, fphtml))
        if r != 0:
            break
    except:
        import traceback
        traceback.print_exc()
        break
    
    
    
    