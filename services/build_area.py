import re,sys;
base="http://gitlab.bitpie.net/devel/bitpie.devel/blob/master/"
s=open(sys.argv[1]).read();
m=s[s.find('<MAP NAME=\"visImageMap\">'):s.find('</MAP>')+6];
m=re.sub('on\w+?=\".+?\"','',m);
m=re.sub('local_service.','../services/local_service.',m);
m=re.sub('%5C','/',m);
m=re.sub('HREF="../','HREF="%s'%base,m);
m=re.sub('HREF="service_','HREF="%s/services/service_'%base,m);
m=re.sub('.vsd','.md',m);
open('area','w').write(m);