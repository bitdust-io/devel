import re,sys;
s=open(sys.argv[1]).read();
m=s[s.find('<MAP NAME=\"visImageMap\">'):s.find('</MAP>')+6];
m=re.sub('on\w+?=\".+?\"','',m);
m=re.sub('%5C','/',m);
m=re.sub('.vsd','.png',m);
open('area','w').write(m);