import json

from namespace import ns

def get_difficulty(obj, data, name_space):
    diff = ns(name_space).db.find("coins", "all")
    if not diff:
        diff = []
    diff = len(diff)/50500 + ns(name_space).base_difficulty
    if diff < ns(name_space).base_difficulty:
        diff = ns(name_space).base_difficulty
    obj.send(json.dumps({"difficulty":diff}))

