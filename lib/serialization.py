

""" 
A possible methods: 
    * pickle 
    * cPickle
    * msgpack
    * jsonpickle
    * yaml
    
Some methods are fast, but libreries needs to be precompiled and distributed.
So I decide to use standard pickle module and upgrade that in future.

"""

#------------------------------------------------------------------------------ 

SERIALIZATION_METHOD = 'pickle' 

#------------------------------------------------------------------------------ 
    

if SERIALIZATION_METHOD == 'pickle':
    import pickle
    
    def ObjectToString(obj):
        """
        """
        return pickle.dumps(obj, protocol=2)
    
    def StringToObject(inp):
        """
        """
        return pickle.loads(inp)
    
    
elif SERIALIZATION_METHOD == 'cPickle':
    import cPickle    

    def ObjectToString(obj):
        """
        """
        return cPickle.dumps(obj, protocol=0)
    
    def StringToObject(inp):
        """
        """
        return cPickle.loads(inp)
    
    
elif SERIALIZATION_METHOD == 'msgpack':
    import msgpack
    
    def ObjectToString(obj):
        """
        """
        return msgpack.dumps(obj)
    
    def StringToObject(inp):
        """
        """
        return msgpack.loads(inp, use_list=False)


#elif SERIALIZATION_METHOD == 'jsonpickle':
#    import json
#    import jsonpickle
#    
#    def ObjectToString(obj):
#        """
#        """
#        return json.dumps(jsonpickle.encode(obj), ensure_ascii=False)
#    
#    def StringToObject(inp):
#        """
#        """
#        return jsonpickle.decode(json.loads(inp))    
    