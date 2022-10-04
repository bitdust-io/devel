import json
import sys
from os import path

import aiohttp
import cachetools.func
import requests
from bismuthclient.bismuthclient import BismuthClient

# Where the wallets and other potential private info are to be stored.
# It's a dir under the user's own home directory.
BISMUTH_PRIVATE_DIR = ".bismuth-private"

HTTP_SESSION = None


def get_private_dir():
    return BismuthClient.user_subdir(BISMUTH_PRIVATE_DIR)


def graph_colors_rgba():
    # https://flatuicolors.com/palette/defo
    return (
        "rgba(211, 84, 0,1.0)",
        "rgba(39, 174, 96,1.0)",
        "rgba(41, 128, 185,1.0)",
        "rgba(142, 68, 173,1.0)",
        "rgba(44, 62, 80,1.0)",
        "rgba(44, 62, 80,1.0)",
        "rgba(243, 156, 18,1.0)",
        "rgba(192, 57, 43,1.0)",
        "rgba(189, 195, 199,1.0)",
        "rgba(127, 140, 141,1.0)",
    )


def base_path():
    """Returns the full path to the current dir, whether the app is frozen or not."""
    if getattr(sys, "frozen", False):
        # running in a bundle
        locale_path = path.dirname(sys.executable)
    else:
        # running live
        locale_path = path.abspath(path.dirname(sys.argv[0]))
    print("Local path", locale_path)
    return locale_path


@cachetools.func.ttl_cache(maxsize=5, ttl=600)
def get_api_10(url, is_json=True):
    """A Cached API getter, with 10 min cache"""
    response = requests.get(url)
    if response.status_code == 200:
        if is_json:
            return response.json()
        else:
            return response.content
    return ""


async def async_get(url, is_json=False, ignore_ssl_errors=False):
    """Async gets an url content.

    If is_json, decodes the content
    """
    # TODO: add an optional cache (custom, since lru and cachetools do not support co-routines)
    global HTTP_SESSION
    # TODO: retry on error?
    if not HTTP_SESSION:
        HTTP_SESSION = aiohttp.ClientSession()
    session = HTTP_SESSION
    if ignore_ssl_errors:
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False))
    try:
        async with session.get(url) as resp:
            if is_json:
                try:
                    return json.loads(await resp.text())
                except Exception as e:
                    print("Error {}".format(e))
                    return None
            else:
                return await resp.text()
            # TODO: could use resp content-type to decide
    except Exception as e:
        print("Async get {}: {}".format(url, e))
        return None


async def async_get_with_http_fallback(https_url, is_json=True):
    data = await async_get(https_url, is_json=is_json)
    if data is None:
        http_url = https_url.replace("https://", "http://")
        data = await async_get(http_url, is_json=is_json, ignore_ssl_errors=True)
    return data


# Unused
"""
def get_content_type(filename: str) -> str:
    # Returns the ``Content-Type`` header to be used for this request.
    mime_type, encoding = mimetypes.guess_type(filename)
    # per RFC 6713, use the appropriate type for a gzip compressed file
    if encoding == "gzip":
        return "application/gzip"
    # As of 2015-07-21 there is no bzip2 encoding defined at
    # http://www.iana.org/assignments/media-types/media-types.xhtml
    # So for that (and any other encoding), use octet-stream.
    elif encoding is not None:
        return "application/octet-stream"
    elif mime_type is not None:
        return mime_type
    # if mime_type not detected, use application/octet-stream
    else:
        return "application/octet-stream"
"""
