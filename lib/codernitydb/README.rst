This repository
===============


This is an intent **to port CodernityDB to Python 3**, from de [original source](http://labs.codernity.com/codernitydb), written for Python 2.x, 

CodernityDB is opensource, pure python (no 3rd party dependency), fast (really fast check Speed in documentation if you don't believe in words), multiplatform, schema-less, NoSQL_ database. It has optional support for HTTP server version (CodernityDB-HTTP), and also Python client library (CodernityDB-PyClient) that aims to be 100% compatible with embeded version.

**Although this port is a beta** yet, it works in the basic usage cases.

Calling for help
================

Any help to port CodernityDB to Python 3 is wellcome. It's a hard works. 

Feel free to clone the repo an send any patch.

Status
======

Following the official examples, I was able to determinate:

- Insert/Save: Works oks!
- Get query: Works oks!
- Duplicates: Works oks!
- Update/delete: Doesn't works yet.
- Ordered data: Doesn't works yet.


Ported examples
===============

There he ported examples:

Insert/Save
-----------

.. code-block:: python

    from CodernityDB3.database import Database

    def main():
        db = Database('/tmp/tut1')
        db.create()
        for x in range(100):
            print(db.insert(dict(x=x)))
        for curr in db.all('id'):
            print(curr)

    main()


Get query
---------

.. code-block:: python

    from CodernityDB3.database import Database
    from CodernityDB3.hash_index import HashIndex


    class WithXIndex(HashIndex):

        def __init__(self, *args, **kwargs):
            kwargs['key_format'] = 'I'
            super(WithXIndex, self).__init__(*args, **kwargs)

        def make_key_value(self, data):
            a_val = data.get("x")
            if a_val is not None:
                return a_val, None
            return None

        def make_key(self, key):
            return key


    def main():
        db = Database('/tmp/tut2')
        db.create()
        x_ind = WithXIndex(db.path, 'x')
        db.add_index(x_ind)

        for x in range(100):
            db.insert(dict(x=x))

        for y in range(100):
            db.insert(dict(y=y))

        print(db.get('x', 10, with_doc=True))        

    if __name__ == '__main__':
        main()
    

Duplicates
----------

.. code-block:: python

    from CodernityDB3.database import Database
    from CodernityDB3.hash_index import HashIndex


    class WithXIndex(HashIndex):

        def __init__(self, *args, **kwargs):
            kwargs['key_format'] = 'I'
            super(WithXIndex, self).__init__(*args, **kwargs)

        def make_key_value(self, data):
            a_val = data.get("x")
            if a_val is not None:
                return a_val, None
            return None

        def make_key(self, key):
            return key


    def main():
        db = Database('/tmp/tut3')
        db.create()
        x_ind = WithXIndex(db.path, 'x')
        db.add_index(x_ind)

        for x in range(100):
            db.insert(dict(x=x))

        for x in range(100):
            db.insert(dict(x=x))

        for y in range(100):
            db.insert(dict(y=y))

        print(db.get('x', 10, with_doc=True))
        for curr in db.get_many('x', 10, limit=-1, with_doc=True):
            print(curr)

    if __name__ == '__main__':
        main()

    
    
Update/delete
-------------

.. code-block:: python

    from CodernityDB3.database import Database
    from CodernityDB3.tree_index import TreeBasedIndex


    class WithXIndex(TreeBasedIndex):

        def __init__(self, *args, **kwargs):
            kwargs['node_capacity'] = 10
            kwargs['key_format'] = 'I'
            super(WithXIndex, self).__init__(*args, **kwargs)

        def make_key_value(self, data):
            t_val = data.get('x')
            if t_val is not None:
                return t_val, None
            return None

        def make_key(self, key):
            return key


    def main():
        db = Database('/tmp/tut_update')
        db.create()
        x_ind = WithXIndex(db.path, 'x')
        db.add_index(x_ind)

        # full examples so we had to add first the data
        # the same code as in previous step

        for x in range(100):
            db.insert(dict(x=x))

        for y in range(100):
            db.insert(dict(y=y))

        # end of insert part

        print(db.count(db.all, 'x'))

        for curr in db.all('x', with_doc=True):
            doc = curr['doc']
            if curr['key'] % 7 == 0:
                db.delete(doc)
            elif curr['key'] % 5 == 0:
                doc['updated'] = True
                db.update(doc)

        print(db.count(db.all, 'x'))

        for curr in db.all('x', with_doc=True):
            print(curr)

    if __name__ == '__main__':
        main()


Ordered
-------

.. code-block:: python

    from CodernityDB3.database import Database
    from CodernityDB3.tree_index import TreeBasedIndex


    class WithXIndex(TreeBasedIndex):

        def __init__(self, *args, **kwargs):
            kwargs['node_capacity'] = 10
            kwargs['key_format'] = 'I'
            super(WithXXIndex, self).__init__(*args, **kwargs)

        def make_key_value(self, data):
            t_val = data.get('x')
            if t_val is not None:
                return t_val, data
            return None

        def make_key(self, key):
            return key


    def main():
        db = Database('/tmp/tut4')
        db.create()
        x_ind = WithXIndex(db.path, 'x')
        db.add_index(x_ind)

        for x in range(11):
            db.insert(dict(x=x))

        for y in range(11):
            db.insert(dict(y=y))

        print(db.get('x', 10, with_doc=True))

        for curr in db.get_many('x', start=15, end=25, limit=-1, with_doc=True):
            print(curr)


    if __name__ == '__main__':
        main()
    
