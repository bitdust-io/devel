#!/usr/bin/python
#terminal_chat.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: terminal_chat
"""

import time
import random
import sys
import termios
import tty
import threading

from twisted.internet import reactor

from lib import nameurl

from chat import kbhit

#------------------------------------------------------------------------------ 

_SimpleTerminalChat = None

#------------------------------------------------------------------------------ 

def init(do_send_message_func=None):
    """
    """
    global _SimpleTerminalChat
    _SimpleTerminalChat = SimpleTerminalChat(
        send_message_func=do_send_message_func)
    

def shutdown():
    """
    """
    global _SimpleTerminalChat
    del _SimpleTerminalChat
    _SimpleTerminalChat = None
    
    
def run():
    """
    """
    global _SimpleTerminalChat
    _SimpleTerminalChat.run()
    reactor.callFromThread(reactor.stop)


def process_message(sender, message):
    """
    """
    global _SimpleTerminalChat
    _SimpleTerminalChat.process_message(sender, message)


def on_incoming_message(result):
    """
    """
    global _SimpleTerminalChat
    for msg in result['result']:
        _SimpleTerminalChat.on_inbox_message(msg['from'], msg['message'])
    return result        

#------------------------------------------------------------------------------ 

class SimpleTerminalChat(object):
    def __init__(self, send_message_func=None):
        self.chars = []
        self.history = []
        self.printed = 0
        self.quitnow = 0
        self.users = []
        self.send_message_func = send_message_func

    def on_inbox_message(self, sender, message):
        name = nameurl.GetName(sender)
        if sender not in self.users:
            self.users.append(sender)
            self.history.append({
                'text': 'user %s was joined' % name,
                'time': time.time(),
            })
        self.history.append({
            'text': message,
            'name': nameurl.GetName(sender),
            'sender': sender,
            'time': time.time(),
        })
    
    def on_my_message(self, message):
        if message.startswith('!add '):
            idurl = message[5:]
            if idurl.strip() and idurl not in self.users:
                self.users.append(idurl)
                name = nameurl.GetName(idurl)
                self.history.append({
                    'text': 'user %s was added' % name,
                    
                    'time': time.time(),
                })
            return
        self.history.append({
            'text': message,
            'name': 'you',
            'time': time.time(),
        })
        if self.send_message_func is not None:
            for to in self.users:
                reactor.callFromThread(self.send_message_func, to, message)
        
    def bot(self):
        while True:
            if self.quitnow:
                break
            time.sleep(0.1)
            if random.randint(1, 100) == 1:
                self.on_inbox_message(
                    'http://p2p-id.ru/bot.xml',
                    'HI man!    ' + time.asctime(),
                )

    def collect_output(self):
        last_line = ''
        while True:
            if self.quitnow:
                break
            time.sleep(0.1)
            if self.printed < len(self.history):
                sys.stdout.write('\b' * (len(last_line)+2))
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

    def collect_input(self):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        kb = kbhit.KBHit()
        try:
            tty.setraw(sys.stdin.fileno())
            sys.stdout.write('> ')
            sys.stdout.flush()
            while 1:
                if self.quitnow:
                    break
                if not kb.kbhit():
                    time.sleep(0.1)
                    continue
                # mod, c = kb.getkeypress()
                mod = None
                c = kb.getch() # .decode('utf-8')
                o = ord(c)
#                 import pdb
#                 pdb.set_trace()
    #             if o <= 31:
    #                 c = kb.getch().decode('utf-8')
    #                 o = ord(c)
                # ESC
                if ord(c) == 27 and mod is None: 
                    sys.stdout.write('\n\r')
                    sys.stdout.flush()
                    self.quitnow = True
                    break
                # UP
                # if c == 'A' and mod is not None:
                #     continue
                # BACKSPACE
                if c == '\x7f' and mod is None:
                    if self.chars:
                        del self.chars[-1]
                        sys.stdout.write('\b \b')
                        sys.stdout.flush()
                        continue
                # ENTER
                if c in '\n\r' and mod is None:
                    msg = ''.join(self.chars)
                    self.chars = []
                    if msg.strip() in ['!q', '!quit', '!exit', ]:
                        sys.stdout.write('\n\r')
                        sys.stdout.flush()
                        self.quitnow = True
                        break
                    sys.stdout.write('\b' * (len(msg)))
                    sys.stdout.flush()
                    self.on_my_message(msg)
                    continue
                # some printable char
                if o >= 32 and o <= 126:
                    sys.stdout.write(c)
                    sys.stdout.flush()
                    self.chars.append(c)
        except KeyboardInterrupt:
            self.quitnow = True
        except Exception as exc:
            import traceback
            traceback.print_exc()
            raise exc
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        kb.set_normal_term()
        return None

    def welcome(self):
        sys.stdout.write('type your message and press Enter to send on channel\n\r')
        sys.stdout.write('use "!add <idurl>" command to invite people here\n\r')
        sys.stdout.write('press ESC or send "!quit" to exit, type "!help" for help\n\r')
        sys.stdout.flush()

    def goodbye(self):
        sys.stdout.write('Good bye!\n\r')
        sys.stdout.flush()

    def run(self):
        self.welcome()
        # bot = threading.Thread(target=self.bot)
        # bot.start()
        out = threading.Thread(target=self.collect_output)
        out.start()
        inp = threading.Thread(target=self.collect_input)
        inp.start()
        inp.join()
        self.goodbye()
