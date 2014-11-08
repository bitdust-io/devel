import re;
s=open('src/services_png_1.htm').read();
m=s[s.find('<MAP NAME=\"visImageMap\">'):s.find('</MAP>')+6];
m=re.sub('on\w+?=\".+?\"', '', m)
open('area','w').write(m);