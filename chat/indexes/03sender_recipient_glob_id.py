# sender_recipient_glob_id
# SenderRecipientGlobID

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
from CodernityDB3.tree_index import TreeBasedIndex

# source of classes in index.classes_code
# classes_code


# index code start

class SenderRecipientGlobID(BaseMD5DoubleKeyIndex):
    role_a = 'sender'
    field_a = 'glob_id'
    role_b = 'recipient'
    field_b = 'glob_id'
