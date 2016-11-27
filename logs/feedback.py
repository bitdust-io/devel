#!/usr/bin/python
# feedback.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (feedback.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
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
MAIL_SERVER_CERTIFICATE_FILE_PATH = '/home/veselin/mail.bitdust.io.cert'
MAIL_SERVER_KEY_FILE_PATH = '/home/veselin/mail.bitdust.io.key'

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
    msg["Date"] = formatdate(localtime=True)
    msg.attach(MIMEText(BODY))
    # attach a file
    for filePath in FILES:
        if not os.path.isfile(filePath):
            continue
        part = MIMEBase('application', "octet-stream")
        part.set_payload(open(filePath, "rb").read())
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(filePath))
        msg.attach(part)
    s = smtplib.SMTP_SSL(HOST, PORT,
                         keyfile=MAIL_SERVER_KEY_FILE_PATH,
                         certfile=MAIL_SERVER_CERTIFICATE_FILE_PATH,
                         timeout=30,)
    # s.set_debuglevel(True) # It's nice to see what's going on
    s.ehlo()  # identify ourselves, prompting server for supported features
    if s.has_extn('STARTTLS'):
        s.starttls()
        s.ehlo()  # re-identify ourse
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
    if 'upload' in form:
        fileitem = form['upload']
    if not subject and not body and not fileitem:
        return False
    files = []
    if fileitem is not None:
        sz = 0
        fout = file(os.path.join('/tmp', fileitem.filename), 'wb')
        while True:
            chunk = fileitem.file.read(100000)
            if not chunk:
                break
            fout.write(chunk)
            sz += len(chunk)
            if sz >= 1024 * 1024 * 50:
                break
        fout.close()
        files.append(os.path.join('/tmp', fileitem.filename))
    settings = open(SETTINGS_FILE_PATH).read().split('\n')[:6]
    settings.extend([subject, body, files, ])
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
