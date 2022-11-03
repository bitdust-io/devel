def default_network_info():
    """
    This file will be automatically overwritten during packaging for PyPi distribution.
    The JSON contents from the "default_network.json" file in the root folder will be inserted here.
    This trick is required to simplify package distribution and exclude "default_network.json" file from the bundle.
    """
    return {}
