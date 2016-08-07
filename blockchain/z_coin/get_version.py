
from namespace import ns

def get_version(obj, data, name_space):
    obj.send(ns(name_space).version)
