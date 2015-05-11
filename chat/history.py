

#------------------------------------------------------------------------------ 

_MessagesCache = {}

#------------------------------------------------------------------------------ 

def store(idurl, msg):
    global _MessagesCache
    if idurl not in _MessagesCache.keys():
        _MessagesCache[idurl] = {}
    _MessagesCache[idurl]

def get_messages():
    pass