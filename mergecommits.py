import sys, os, re, time, pprint

h1=open(sys.argv[1]).read().splitlines()
h2=open(sys.argv[2]).read().splitlines()
h1times = {}
h2times = {}

for commit1 in h1:
    dt1 = re.search('\[(.+?)\]', commit1)
    if dt1:
        dt1 = time.mktime(time.strptime(dt1.group(1)[:-6]))
        h1times[dt1] = commit1

for commit2 in h2:
    dt2 = re.search('\[(.+?)\]', commit2)
    if dt2:
        dt2 = time.mktime(time.strptime(dt2.group(1)[:-6]))
        h2times[dt2] = commit2

h1sorted = sorted(h1times.keys(), reverse=True)
h2sorted = sorted(h2times.keys(), reverse=True)

tcurr = time.time()

parts = {}
parts[-1] = []
parts[-1].append((tcurr, '123456 [date] !!! NOT PUBLISHED YET !!!'))

for i in xrange(len(h2sorted)):
    dt2 = h2sorted[i]
    commit2 = h2times[dt2]
    parts[i] = []
    parts[i].append((dt2, commit2))
    for dt1 in h1sorted:
        commit1 = h1times[dt1]
        if dt1 < tcurr and dt1 > dt2:
            parts[i-1].append((dt1, commit1))
    tcurr = dt2

for i in sorted(parts.keys(), reverse=False):
    commits = parts[i]
    headcommit = commits.pop(0)
    print '[%s]' % time.asctime(time.localtime(headcommit[0])) 
    print re.match('\w+? \[.+?\] (.+?)$', headcommit[1]).group(1)
    for dt, commit in commits:
        print '    [%s] %s' % (time.strftime('%c', time.localtime(dt)), 
                               re.match('\w+? \[.+?\] (.+?)$', commit).group(1))
    print