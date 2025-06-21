#!/usr/bin/python
# terminal_chat.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (terminal_chat.py) is part of BitDust Software.
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
"""
..

module:: terminal_chat
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
import time
import random
import sys
import termios
import tty
import threading

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

_Debug = False

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from bitdust.lib import nameurl

from bitdust.userid import global_id

from bitdust.chat import kbhit

#------------------------------------------------------------------------------

_TerminalChat = None

#------------------------------------------------------------------------------


def init(do_send_message_func=None, do_search_user_func=None):
    global _TerminalChat
    _TerminalChat = TerminalChat(
        send_message_func=do_send_message_func,
        search_user_func=do_search_user_func,
    )


def shutdown():
    global _TerminalChat
    del _TerminalChat
    _TerminalChat = None


def run(on_stop=None):
    global _TerminalChat
    _TerminalChat.run()
    if _Debug:
        print('before on_stop')
    if on_stop:
        reactor.callFromThread(on_stop)  # @UndefinedVariable
    if _Debug:
        print('after on_stop')


def stop():
    global _TerminalChat
    _TerminalChat.stop()


def process_message(sender, message):
    global _TerminalChat
    _TerminalChat.process_message(sender, message)


def on_incoming_message(msg):
    global _TerminalChat
    _TerminalChat.on_inbox_message(msg['sender'], msg)
    return msg


#------------------------------------------------------------------------------


class TerminalChat(object):

    def __init__(self, send_message_func=None, search_user_func=None):
        self.chars = []
        self.input = []
        self.history = []
        self.printed = 0
        self.quitnow = False
        self.users = []
        self.send_message_func = send_message_func
        self.search_user_func = search_user_func

    def on_inbox_message(self, sender, message):
        if _Debug:
            print('on_inbox_message', sender, message)
        name = nameurl.GetName(sender)
        if sender not in self.users:
            self.users.append(sender)
            self.history.append({
                'text': 'user %s joined' % name,
                'name': '',
                'time': time.time(),
            })
        self.history.append({
            'text': (message.get('data') or {}).get('terminal_chat_message') or '',
            'name': nameurl.GetName(sender),
            'sender': sender,
            'time': time.time(),
        })

    def on_nickname_search_result(self, results):
        if results['status'] != 'OK':
            self.history.append({
                'text': 'search failed: %s' % results['errors'],
                'name': '',
                'time': time.time(),
            })
            return None
        for r in results['result']:
            self.history.append({
                'text': '%s' % (r['idurl'] if r.get('idurl') else 'not found'),
                'name': '',
                'time': time.time(),
            })

    def on_my_message(self, message):
        if message.startswith('!add '):
            idurl = message[5:].strip()
            if global_id.IsValidGlobalUser(idurl):
                gid = global_id.NormalizeGlobalID(idurl, as_field=False)
                idurl = gid['idurl']
            if idurl and idurl not in self.users:
                self.users.append(idurl)
                name = nameurl.GetName(idurl)
                self.history.append({
                    'text': 'user "%s" was added to the channel' % name,
                    'name': '',
                    'time': time.time(),
                })
            return
        if message.startswith('!find ') or message.startswith('!search '):
            _, _, inp = message.partition(' ')
            if not self.search_user_func:
                self.history.append({
                    'text': 'search failed, method not defined',
                    'name': '',
                    'time': time.time(),
                })
                return
            self.search_user_func(inp).addBoth(self.on_nickname_search_result)
            self.history.append({
                'text': 'looking for "%s" ...' % inp,
                'name': '',
                'time': time.time(),
            })
            return
        self.history.append({
            'text': message,
            'name': 'you',
            'time': time.time(),
        })
        if self.send_message_func is not None:
            if _Debug:
                print('sending %d bytes to %r' % (len(message), self.users))
            for to in self.users:
                reactor.callFromThread(self.send_message_func, str(to), {'terminal_chat_message': message})  # @UndefinedVariable

    def bot(self):
        while True:
            if self.quitnow:
                break
            time.sleep(0.1)
            if random.randint(1, 500) == 1:
                self.on_inbox_message(
                    'http://p2p-id.ru/bot.xml',
                    'HI man!    ' + time.asctime(),
                )
        if _Debug:
            print('bot thread ended')
        return None

    def collect_output(self):
        try:
            last_line = ''
            sys.stdout.write('> ')
            sys.stdout.flush()
            while True:
                if self.quitnow:
                    break
                time.sleep(0.05)
                if self.printed < len(self.history):
                    sys.stdout.write('\b'*(len(last_line) + 2))
                    # sys.stdout.write('\n\r')
                    sys.stdout.flush()
                    for h in self.history[self.printed:]:
                        out = ''
                        if h.get('time'):
                            out += '[%s] ' % time.strftime('%H:%M:%S', time.gmtime(h['time']))
                        if h.get('name'):
                            out += h['name'] + ': '
                        out += h.get('text', '')
                        last_line = out
                        sys.stdout.write(out + '\n\r')
                        sys.stdout.flush()
                    sys.stdout.write('> ' + (''.join(self.chars)))
                    sys.stdout.flush()
                    self.printed = len(self.history)
        except Exception as exc:
            self.quitnow = True
            if _Debug:
                print('collect_output thread failed: %r' % exc)
        if _Debug:
            print('collect_output thread ended')
        return None

    def collect_input(self):
        try:
            while True:
                if self.quitnow:
                    break
                ch = self.kb.getch()
                self.input.append(ch)
        except KeyboardInterrupt:
            self.quitnow = True
        if _Debug:
            print('collect_input thread ended')
        return None

    def process_input(self):
        try:
            while True:
                if self.quitnow:
                    break
                if len(self.input) == 0:
                    time.sleep(0.05)
                    continue
                inp = list(self.input)
                self.input = []
                # COMBINATION OR SPECIAL KEY PRESSED
                if len(inp) == 3 and ord(inp[0]) == 27:
                    continue
                for c in inp:
                    # ESC
                    if ord(c) == 27:
                        sys.stdout.write('\n\r')
                        sys.stdout.flush()
                        self.quitnow = True
                        break
                    # BACKSPACE
                    if c == '\x7f':
                        if self.chars:
                            del self.chars[-1]
                            sys.stdout.write('\b \b')
                            sys.stdout.flush()
                            continue
                    # ENTER
                    if c in '\n\r':
                        if len(self.chars) == 0:
                            continue
                        msg = ''.join(self.chars)
                        self.chars = []
                        if msg.strip() in ['!q', '!quit', '!exit']:
                            sys.stdout.write('\n\r')
                            sys.stdout.flush()
                            self.quitnow = True
                            break
                        sys.stdout.write('\b'*(len(msg)))
                        sys.stdout.flush()
                        self.on_my_message(msg)
                        continue
                    # some printable char
                    if ord(c) >= 32 and ord(c) <= 126:
                        sys.stdout.write(c)
                        sys.stdout.flush()
                        self.chars.append(c)
        except Exception as exc:
            if _Debug:
                print('process_input thread failed: %r' % exc)
            self.quitnow = True
        if _Debug:
            print('process_input thread ended')
        return None

    def welcome(self):
        sys.stdout.write('press Enter to send a message to the channel\n\r')
        sys.stdout.write('use "!add <idurl>" command to invite people here\n\r')
        sys.stdout.write('press ESC or send "!q" to quit\n\r')
        sys.stdout.flush()

    def goodbye(self):
        sys.stdout.write('\n\rchat session ended\n\r')
        sys.stdout.flush()

    def run(self):
        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)
        self.kb = kbhit.KBHit()
        tty.setraw(sys.stdin.fileno())

        self.welcome()
        # bot = threading.Thread(target=self.bot)
        # bot.start()
        out = threading.Thread(target=self.collect_output)
        out.start()
        inp = threading.Thread(target=self.collect_input)
        inp.start()
        proc = threading.Thread(target=self.process_input)
        proc.start()
        proc.join()
        self.goodbye()

        try:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
            self.kb.set_normal_term()
        except Exception as exc:
            if _Debug:
                print('run thread failed: %r' % exc)
        if _Debug:
            print('run thread ended')

    def stop(self):
        self.quitnow = True


#------------------------------------------------------------------------------

if __name__ == '__main__':
    init()
    reactor.callInThread(run)  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable
    shutdown()
