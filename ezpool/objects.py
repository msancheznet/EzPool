import Pyro4
import sys
from multiprocessing import Process
from utils import split_uri

@Pyro4.expose
class Closeable(object):
	""" Define a base class that allows any Pyro4 object to be
		closed remotely through the `shutdown` method

		:ivar Pyro4.core.daemon _daemon: Reference to the thread that is running this object
	"""
	def __init__(self, daemon):
		self._daemon = daemon

	@Pyro4.oneway   # in case call returns much later than daemon.shutdown
	def shutdown(self):
		""" Shutdown this object from a proxy by shutting down its daemon """
		print('Shutting down object...')
		self._daemon.shutdown()

def run_object(cls, args=None):
	""" Run a Pyro4 object with a set of arguments
		
		:param class cls: Class that will be run as a Pyro object in a deamon
		:param args: Arguements to parse by the object

		.. Warning:: Cls will be tagged as exposed by default
	"""
	if cls is None:
		raise TypeError('NoneType cannot be run as Pyro deamon')

	# Get the configuration parameters to run this object
	args = cls.parse_args(args=args)
	if args.uri != '':
		args.name, args.address, args.port = split_uri(args.uri)

	# Create the deamon thread and the object
	daemon = Pyro4.Daemon(host=args.address, port=args.port)
	cls    = Pyro4.expose(cls)
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

def spawn_object(cls, args=None):
	""" Spawn a new process and run the object in there.

		:param class cls: Class that will be run as a Pyro object in a deamon
		:param args: Arguements to parse by the object
		:param Process: The new process where the object is run
	"""
	p = Process(target=run_object, args=(cls, args))
	p.start()
	return p