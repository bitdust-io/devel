#!/usr/bin/python
#feedback.py
#
# <<<COPYRIGHT>>>
#
#
#
#

import cgi
import cgitb
cgitb.enable(0, '/tmp', 10, 'text')

import os
import sys
import time

#------------------------------------------------------------------------------ 

SETTINGS_FILE_PATH = '/home/veselin/feedback.conf'

#------------------------------------------------------------------------------ 

def SendEmail(args_9_tuple):
    (TO, FROM, HOST, PORT, LOGIN, PASSWORD, SUBJECT, BODY, FILES) = args_9_tuple
    PORT = int(PORT)
    import smtplib
    from email import Encoders
    from email.MIMEText import MIMEText
    from email.MIMEBase import MIMEBase
    from email.MIMEMultipart import MIMEMultipart
    from email.Utils import formatdate

    msg = MIMEMultipart()
    msg["From"] = FROM
    msg["To"] = TO
    msg["Subject"] = SUBJECT
    msg["Date"]    = formatdate(localtime=True)
    msg.attach(MIMEText(BODY))
    # attach a file
    for filePath in FILES:
        if not os.path.isfile(filePath):
            continue
        part = MIMEBase('application', "octet-stream")
        part.set_payload( open(filePath,"rb").read() )
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(filePath))
        msg.attach(part)
    s = smtplib.SMTP(HOST, PORT)
    # s.set_debuglevel(True) # It's nice to see what's going on
    s.ehlo() # identify ourselves, prompting server for supported features
    if s.has_extn('STARTTLS'):
        s.starttls()
        s.ehlo() # re-identify ourse
    s.login(LOGIN, PASSWORD)  # optional
    failed = s.sendmail(FROM, TO, msg.as_string())
    s.close()
    return failed


def print_html_response(txt):
    print "content-type: text/html\n"
    print "<html>%s</html>" % txt

def save_uploaded_file():
    form = cgi.FieldStorage()
    subject = form.getvalue('subject', '')
    body = form.getvalue('body', '')[:65000]
    fileitem = None
    if form.has_key('upload'): 
        fileitem = form['upload']
    if not subject and not body and not fileitem:
        return False
    files = []
    if fileitem is not None:
        sz = 0
        fout = file(os.path.join('/tmp', fileitem.filename), 'wb')
        while 1:
            chunk = fileitem.file.read(100000)
            if not chunk: 
                break
            fout.write(chunk)
            sz += len(chunk)
            if sz >= 1024*1024*50:
                break
        fout.close()
        files.append(os.path.join('/tmp', fileitem.filename))
    settings = open(SETTINGS_FILE_PATH).read().split('\n')[:6]
    settings.extend([subject, body, files,])
    settings = tuple(settings)
    SendEmail(settings)
    return True

if __name__ == '__main__':
#    settings = open('test.conf').read().split('\n')[:6]
#    settings.extend(['test', 'test\ntest\ntest', [],])
#    settings = tuple(settings)
#    SendEmail(settings)
    if not save_uploaded_file():
        print_html_response('ready')
    else:
        print_html_response('done')
    
    