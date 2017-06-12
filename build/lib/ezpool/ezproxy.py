import Pyro4
from objects import spawn_object
from utils import is_connected, get_uri, get_location, split_uri

class EzProxy(Pyro4.Proxy):
	""" Convience subclass of Pyro's Proxy object that facilitates
		working with proxies by implementing common operations
	"""
	@property
	def connected(self):
		""" True if this proxy is reachable """
		return is_connected(self)

	@property
	def uri(self):
		""" URI for this proxy """
		return get_uri(self)

	@property
	def location(self):
		""" Tuple with (address, port, object name) """
		return get_location(self)

	@property
	def name(self):
		""" Proxy name """
		_, _, name = self.location
		return name

	def close(self):
		""" Close a proxy by releasing the Pyro connection """
		self._pyroRelease()

def connect_to(uri, obj_cls):
	""" Connect to a URI and return its proxy. If the URI is in localhost and the object is not available, spawn a new process and run it there.

		:param str URI: The URI to connect to
		:param class obj_cls: Class that will be run inside the Pyro object in a deamon
		:return tuple: (Proxy, Process)
	"""
	# Try to reach the object
	obj = EzProxy(uri)
	_, address, _ = split_uri(uri)
	prc = None

	# If the proxy couldn't connect and the address is localhost, spawn automatically
	if not obj.connected:
		if address == 'localhost' and obj_cls is not None:
			prc = spawn_object(obj_cls, ['-u {}'.format(uri)])
			obj = EzProxy(uri)
					
			print('WARNING:: Opening default {} at {}'.format(obj.name, obj.uri))
		else:
			raise TypeError('Unreachable object at {}'.format(uri))

	return (obj, prc)