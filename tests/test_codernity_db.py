import six
import time
import os

from unittest import TestCase


if six.PY2:
    from CodernityDB.database import Database
    from CodernityDB.hash_index import HashIndex
    from CodernityDB.tree_index import TreeBasedIndex

else:
    from CodernityDB3.database import Database
    from CodernityDB3.hash_index import HashIndex
    from CodernityDB3.tree_index import TreeBasedIndex


class WithXTreeIndex(TreeBasedIndex):

    def __init__(self, *args, **kwargs):
        kwargs['node_capacity'] = 10
        kwargs['key_format'] = 'I'
        super(WithXTreeIndex, self).__init__(*args, **kwargs)

    def make_key_value(self, data):
        t_val = data.get('x')
        if t_val is not None:
            return t_val, None
        return None

    def make_key(self, key):
        return key


class WithXHashIndex(HashIndex):

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = 'I'
        super(WithXHashIndex, self).__init__(*args, **kwargs)

    def make_key_value(self, data):
        a_val = data.get("x")
        if a_val is not None:
            return a_val, None
        return None

    def make_key(self, key):
        return key


def create_test_db(db_name='codernity_test_db_0', with_x_hash_index=False, with_x_tree_index=False):
    t = time.time()
    db_path = '/tmp/%s' % db_name
    os.system('rm -rf %s' % db_path)
    db = Database(db_path)
    db.create()
    if with_x_hash_index:
        x_ind = WithXHashIndex(db.path, 'x')
        db.add_index(x_ind)
    if with_x_tree_index:
        x_ind = WithXTreeIndex(db.path, 'x')
        db.add_index(x_ind)
    print('\ncreate_test_db finished in %f sec' % (time.time() - t))
    return db


class TestCodernityDB(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_insert_save_store(self):
        _db = create_test_db(db_name='codernity_test_db_1', with_x_hash_index=True)
        for x in range(100):
            assert _db.insert(dict(x=x)) is not None
        x = 0
        for curr in _db.all('id'):
            assert curr['x'] == x
            x += 1

    def test_get_query(self):
        _db = create_test_db(db_name='codernity_test_db_2', with_x_hash_index=True)
        for x in range(100):
            _db.insert(dict(x=x))
        for y in range(100):
            _db.insert(dict(y=y))
        assert _db.get('x', 10, with_doc=True)['doc']['x'] == 10

    def test_deduplicates(self):
        _db = create_test_db(db_name='codernity_test_db_3', with_x_hash_index=True)
        for x in range(100):
            _db.insert(dict(x=x))
        for x in range(100):
            _db.insert(dict(x=x))
        for y in range(100):
            _db.insert(dict(y=y))
        assert _db.get('x', 10, with_doc=True)['doc']['x'] == 10
        assert len([i for i in _db.get_many('x', 10, limit=-1, with_doc=True)]) == 2

    def test_update_delete(self):
        _db = create_test_db(db_name='codernity_test_db_4', with_x_tree_index=True)
        for x in range(100):
            _db.insert(dict(x=x))
        for y in range(100):
            _db.insert(dict(y=y))
        assert _db.count(_db.all, 'x') == 100
        for curr in _db.all('x', with_doc=True):
            doc = curr['doc']
            if curr['key'] % 9 == 0:
                _db.delete(doc)
            elif curr['key'] % 5 == 0:
                doc['updated'] = True
                _db.update(doc)
        _db.reindex()
        total = _db.count(_db.all, 'x')
        assert total == 88

    def test_ordered(self):
        _db = create_test_db(db_name='codernity_test_db_5', with_x_tree_index=True)
        for x in range(11):
            _db.insert(dict(x=x))
        for y in range(11):
            _db.insert(dict(y=y))
        assert _db.get('x', 10, with_doc=True)['doc']['x'] == 10
        for curr in _db.get_many('x', start=3, end=8, limit=-1, with_doc=True):
            assert curr['doc']['x'] >= 3
