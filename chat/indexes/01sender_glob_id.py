# sender_glob_id
# SenderGlobID

# inserted automatically
import os
import marshal

import struct
import shutil

from hashlib import md5

# custom db code start
# db_custom

from chat.message_index import BaseTimeIndex
from chat.message_index import BaseMD5Index
from chat.message_index import BaseMD5DoubleKeyIndex

# custom index code start
# ind_custom


# source of classes in index.classes_code
# classes_code


# index code start

class SenderGlobID(BaseMD5Index):
    role = 'sender'
    field = 'glob_id'
