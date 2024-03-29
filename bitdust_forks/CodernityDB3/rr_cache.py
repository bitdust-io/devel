#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011-2013 Codernity (http://codernity.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
import six
import functools
from random import choice
from six.moves import range


def cache1lvl(maxsize=100):
    def decorating_function(user_function):
        cache1lvl = {}

        @functools.wraps(user_function)
        def wrapper(key, *args, **kwargs):
            # print('rr_cache.1lvl.wrapper %r %r' % (user_function, key))
            if isinstance(key, six.text_type):
                key = key.encode()
            try:
                result = cache1lvl[key]
                # print('rr_cache.1lvl.wrapper found result')
            except KeyError:
                if len(cache1lvl) == maxsize:
                    for i in range(maxsize // 10 or 1):
                        del cache1lvl[choice(list(cache1lvl.keys()))]
                cache1lvl[key] = user_function(key, *args, **kwargs)
                result = cache1lvl[key]
            return result

        def clear():
            cache1lvl.clear()

        def delete(key):
            # print('rr_cache.1lvl.delete %r %r' % (user_function, key))
            if isinstance(key, six.text_type):
                key = key.encode()
            try:
                del cache1lvl[key]
                return True
            except KeyError:
                return False

        wrapper.clear = clear
        wrapper.cache = cache1lvl
        wrapper.delete = delete
        return wrapper
    return decorating_function


def cache2lvl(maxsize=100):
    def decorating_function(user_function):
        cache = {}

        @functools.wraps(user_function)
        def wrapper(*args, **kwargs):
#            return user_function(*args, **kwargs)
            key = args[0]
            # print('rr_cache.2lvl.wrapper %r %r' % (user_function, key))
            if isinstance(key, six.text_type):
                key = key.encode()
            try:
                result = cache[key][args[1]]
                # print('rr_cache.2lvl.wrapper found result')
            except KeyError:
                if wrapper.cache_size == maxsize:
                    to_delete = maxsize // 10 or 1
                    for i in range(to_delete):
                        key1 = choice(list(cache.keys()))
                        key2 = choice(list(cache[key1].keys()))
                        del cache[key1][key2]
                        if not cache[key1]:
                            del cache[key1]
                    wrapper.cache_size -= to_delete
                result = user_function(*args, **kwargs)
                try:
                    cache[key][args[1]] = result
                except KeyError:
                    cache[key] = {args[1]: result}
                wrapper.cache_size += 1
            return result

        def clear():
            cache.clear()
            wrapper.cache_size = 0

        def delete(key, inner_key=None):
            # print('rr_cache.2lvl.delete %r %r' % (user_function, key))
            if isinstance(key, six.text_type):
                key = key.encode()
            if inner_key:
                try:
                    del cache[key][inner_key]
                    if not cache[key]:
                        del cache[key]
                    wrapper.cache_size -= 1
                    return True
                except KeyError:
                    return False
            else:
                try:
                    wrapper.cache_size -= len(cache[key])
                    del cache[key]
                    return True
                except KeyError:
                    return False

        wrapper.clear = clear
        wrapper.cache = cache
        wrapper.delete = delete
        wrapper.cache_size = 0
        return wrapper
    return decorating_function
