import time
import random
import sys
import termios
import tty

import kbhit

chars = []
hist = []
printed = 0
quit = 0

def get_line(prompt):
    sys.stdout.write(prompt)
    sys.stdout.flush()
    line = sys.stdin.readline()
    if line:
        return line[:-1]
    return ''

def handle(msg):
    global hist
    hist.append(("you", msg))
    
def bot_process():
    global quit
    global hist
    while True:
        if quit:
            break
        time.sleep(0.1)
        if random.randint(1, 100) == 1:
            hist.append(('random bot', 'HI man!    ' + time.asctime()))

def collect_output():
    global hist
    global printed
    global quit
    global chars
    while True:
        if quit:
            break
        time.sleep(0.1)
#         if hist and hist[-1][0] == 'you' and hist[-1][1].strip() == 'q':
#             return None
        if printed < len(hist):
            sys.stdout.write('\b' * (len(chars)+2))
            sys.stdout.flush()
            for h in hist[printed:]:
                sys.stdout.write(h[0] + ': ' + h[1] + '\n\r')
                sys.stdout.flush()
            sys.stdout.write('> ' + (''.join(chars)))
            sys.stdout.flush()
            # out = [w[0]+": " + w[1] for w in hist[printed:]]
            # sys.stdout.write(('\n'.join(out)))
            # sys.stdout.write('\n')
            # sys.stdout.flush()
            printed = len(hist)
    
def collect_input():
    global chars
    global quit
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    kb = kbhit.KBHit()
    try:
        tty.setraw(sys.stdin.fileno())
        sys.stdout.write('> ')
        sys.stdout.flush()
        while 1:
            if quit:
                break
            if not kb.kbhit():
                continue
            c = kb.getch().decode('utf-8')
            o = ord(c)
#             if o <= 31:
#                 c = kb.getch().decode('utf-8')
#                 o = ord(c)
            # ESC
            if ord(c) == 27: 
                sys.stdout.write('\n\r')
                sys.stdout.flush()
                quit = True
                break
            # UP
            if c == '\x1b':
                continue
            # BACKSPACE
            if c == '\x7f':
                if chars:
                    del chars[-1]
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
                    continue
            # ENTER
            if c in '\n\r':
                msg = ''.join(chars)
                chars = []
                if msg.strip() == 'quit':
                    sys.stdout.write('\n\r')
                    sys.stdout.flush()
                    quit = True
                    break
                sys.stdout.write('\b' * (len(msg)))
                sys.stdout.flush()
                handle(msg)
                continue
            # some printable char
            if o >= 32 and o <= 126:
                sys.stdout.write(c)
                sys.stdout.flush()
                chars.append(c)
    except KeyboardInterrupt:
        quit = True
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise exc
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    kb.set_normal_term()
    return None


import threading

print 'type message and press Enter to send to the channel'
print 'press ESC or send "quit" to exit'

bot = threading.Thread(target=bot_process)
bot.start()

out = threading.Thread(target=collect_output)
out.start()

inp = threading.Thread(target=collect_input)
inp.start()

