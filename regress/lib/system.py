import os

#------------------------------------------------------------------------------

_Debug = True

#------------------------------------------------------------------------------

from lib import strng

#------------------------------------------------------------------------------

def WriteTextFile(filepath, data):
    """
    A smart way to write data into text file. Return True if success.
    This should be atomic operation - data is written to another temporary file and than renamed.
    """
    temp_path = filepath + '.tmp'
    if os.path.exists(temp_path):
        if not os.access(temp_path, os.W_OK):
            return False
    if os.path.exists(filepath):
        if not os.access(filepath, os.W_OK):
            return False
        try:
            os.remove(filepath)
        except Exception as e:
            if _Debug:
                print('file %r write failed: %r' % (filepath, e, ))
            return False
    fout = open(temp_path, 'wt', encoding='utf-8')
    text_data = strng.to_text(data)
    fout.write(text_data)
    fout.flush()
    os.fsync(fout)
    fout.close()
    try:
        os.rename(temp_path, filepath)
    except Exception as e:
        if _Debug:
            print('file %r write failed: %r' % (filepath, e, ))
        return False
    return True


def ReadTextFile(filename):
    """
    Read text file and return its content.
    """
    if not os.path.isfile(filename):
        return u''
    if not os.access(filename, os.R_OK):
        return u''
    try:
        infile = open(filename, 'rt', encoding="utf-8")
        data = infile.read()
        infile.close()
        return data
    except Exception as e:
        if _Debug:
            print('file %r read failed: %r' % (filename, e, ))
    return u''

#------------------------------------------------------------------------------

def WriteBinaryFile(filename, data):
    """
    A smart way to write data to binary file. Return True if success.
    """
    try:
        f = open(filename, 'wb')
        f.write(data)
        f.flush()
        # from http://docs.python.org/library/os.html on os.fsync
        os.fsync(f.fileno())
        f.close()
    except Exception as e:
        if _Debug:
            print('file %r write failed: %r' % (filename, e, ))
        try:
            # make sure file gets closed
            f.close()
        except:
            pass
        return False
    return True


def ReadBinaryFile(filename, decode_encoding=None):
    """
    A smart way to read binary file. Return empty string in case of:

    - path not exist
    - process got no read access to the file
    - some read error happens
    - file is really empty
    """
    if not filename:
        return b''
    if not os.path.isfile(filename):
        return b''
    if not os.access(filename, os.R_OK):
        return b''
    try:
        infile = open(filename, mode='rb')
        data = infile.read()
        if decode_encoding is not None:
            data = data.decode(decode_encoding)
        infile.close()
        return data
    except Exception as e:
        if _Debug:
            print('file %r read failed: %r' % (filename, e, ))
    return b''

#------------------------------------------------------------------------------

def rmdir_recursive(dirpath, ignore_errors=False, pre_callback=None):
    """
    Remove a directory, and all its contents if it is not already empty.

    http://mail.python.org/pipermail/python-
    list/2000-December/060960.html If ``ignore_errors`` is True process
    will continue even if some errors happens. Method ``pre_callback``
    can be used to decide before remove the file.
    """
    counter = 0
    for name in os.listdir(dirpath):
        full_name = os.path.join(dirpath, name)
        # on Windows, if we don't have write permission we can't remove
        # the file/directory either, so turn that on
        if not os.access(full_name, os.W_OK):
            try:
                os.chmod(full_name, 0o600)
            except:
                continue
        if os.path.isdir(full_name):
            counter += rmdir_recursive(full_name, ignore_errors, pre_callback)
        else:
            if pre_callback:
                if not pre_callback(full_name):
                    continue
            if os.path.isfile(full_name):
                if not ignore_errors:
                    os.remove(full_name)
                    counter += 1
                else:
                    try:
                        os.remove(full_name)
                        counter += 1
                    except Exception as exc:
                        if _Debug:
                            print('rmdir_recursive', exc)
                        continue
    if pre_callback:
        if not pre_callback(dirpath):
            return counter
    if not ignore_errors:
        os.rmdir(dirpath)
    else:
        try:
            os.rmdir(dirpath)
        except Exception as exc:
            if _Debug:
                print('rmdir_recursive', exc)
    return counter
