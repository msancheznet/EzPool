import Pyro4
import sys
if sys.version_info >= (3, 4):
	from abc import ABC, abstractmethod
else:
	from abc import ABCMeta, abstractmethod
from utils import is_connected, get_uri, get_location

class EzProxy(Pyro4.Proxy):
	""" Convience subclass of Pyro's Proxy object that facilitates
		working with proxies by implementing common operations
	"""
	@property
	def connected(self):
		""" Returns true if this proxy is reachable """
		return is_connected(self)

	@property
	def uri(self):
		""" Retur the URI for this proxy """
		return get_uri(self)

	@property
	def location(self):
		""" Return a tuple (address, port, object name) """
		return get_location(self)

@Pyro4.expose
class Closeable(object):
	""" Define a base class that allows any Pyro4 object to be
		closed remotely through the `shutdown` method

		:ivar Pyro4.core.daemon: Reference to the thread that is running this object
	"""
	def __init__(self, daemon):
		self._daemon = daemon

	@Pyro4.oneway   # in case call returns much later than daemon.shutdown
	def shutdown(self):
		print('Shutting down object...')
		self._daemon.shutdown()

""" Define an abstract class Worker that enforces everyone
	implementing the `run` method.

	.. Tip:: The implementation depends on the version of Python
"""
if sys.version_info >= (3, 4):
	@Pyro4.expose
	class Worker(Closeable, ABC):
		@abstractmethod
		def run(self):
			pass
		@property
		def is_worker(self):
			return True
elif (3, 0) <= sys.version_info < (3, 4):
	@Pyro4.expose
	class Worker(Closeable, metaclass=ABCMeta):
		@abstractmethod
		def run(self):
			pass
		@property
		def is_worker(self):
			return True
else:
	@Pyro4.expose
	class Worker(Closeable):
		__metaclass__ = ABCMeta

		@abstractmethod
		def run(self):
			pass
		@property
		def is_worker(self):
			return True

def run_object(cls, args):
    """ Run a Pyro4 object with a set of arguments
        
        :param class cls: Class that will be run as a Pyro object in a deamon
        :param args: Result of argparse.ArgumentParser().parse_args() to have a standard interface
    """
    # Create the deamon thread and the object
    daemon = Pyro4.Daemon(host=args.address, port=args.port)
    obj    = cls(daemon)
    if not isinstance(obj, Closeable):
        daemon.close()
        raise TypeError('{} must be a subclass of objects.Closeable'.format(cls))
    
    # Register the object
    uri = daemon.register(obj, objectId=args.name)

    # Display message to advertise worker's location
    print(args.msg)
    print('   {}'.format(uri))
    print('Pyro daemon running.')
    
    # Enter the loop to wait for jobs
    daemon.requestLoop()

    # If you reach this point it means that the deamon has been
    # closed remotely
    daemon.close()