import os
import time
import Pyro4
from Pyro4.errors import CommunicationError, ConnectionClosedError
from subprocess import Popen, PIPE, STDOUT
from threading import Thread
import multiprocessing as mp

def is_connected(proxy):
    ''' Check if a Pyro4 proxy is available thorugh the network

        :param Pyro4.Proxy proxy: 
        :return bool: True if proxy can communication with remote object
    '''
    try:
        proxy._pyroBind()
    except (CommunicationError, ConnectionClosedError):
        return False
    else:
        return True

def get_uri(proxy):
    """ Get the URI from a proxy

        :param Pyro4.Proxy proxy: 
        :return str URI: E.g. PYRO:object@localhost:20000
    """
    return proxy._pyroUri.asString()

def get_location(proxy):
    """ Get the location of a URI decomposed as tuple

        :param Pyro4.Proxy proxy: 
        :return tuple: E.g. (IP address, TCP port, object_id)
    """
    return (proxy._pyroUri.host, proxy._pyroUri.port, proxy._pyroUri.object)

def split_uri(uri):
    """ Decompose a URI into its constituents
        
        :param str URI: The URI to decompose
        :return tuple: (name, address, port)
    """
    name, address, port = uri.replace('@',':').split(':')[1:]
    return (name, address, int(port))

def sec2hms(seconds):
    """ Convert seconds to readable hour:minute:sec format 

        :param float seconds: Seconds

        :return str: The nicely formatted string
    """
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return "%dh:%02dm:%02ds" % (h, m, s)

class LogFun(object):
    """ Function wrapper to log its exceptions and execution time
        
        :ivar function _fun: The function to be wrapped

        .. code-block:: python
            :linenos:

            def echo(task):
                return task

            res, t_elapsed = LogFun(echo)(0)
    """
    def __init__(self, fun):
        """ Initialize the logger

            :param function fun: Function to be wrapped
        """
        self._fun = fun

    def __call__(self, *args, **kwargs):
        """ Make this class callable by forwarding the call to the wrapped function. 

            :returns tuple: (result of function call, time elapsed)
        """
        tstart   = time.time()
        try:
            res = self._fun(*args, **kwargs)
        except Exception as err:
            res = err
        return res, sec2hms(time.time() - tstart)
