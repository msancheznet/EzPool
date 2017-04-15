import Pyro4
import sys
if sys.version_info >= (3, 4):
	from abc import ABC, abstractmethod
else:
	from abc import ABCMeta, abstractmethod
from utils import is_connected	

""" Define an abstract class Worker that enforces everyone
	implementing the `run` method.

	.. Tip:: The implementation depends on the version of Python
"""
if sys.version_info >= (3, 4):
	@Pyro4.expose
	class Worker(ABC):
		@abstractmethod
		def run(self):
			pass
		@property
		def is_worker(self):
			return True
elif (3, 0) <= sys.version_info < (3, 4):
	@Pyro4.expose
	class Worker(metaclass=ABCMeta):
		@abstractmethod
		def run(self):
			pass
		@property
		def is_worker(self):
			return True
else:
	@Pyro4.expose
	class Worker:
		__metaclass__ = ABCMeta

		@abstractmethod
		def run(self):
			pass
		@property
		def is_worker(self):
			return True

class EzProxy(Pyro4.Proxy):
	@property
	def connected(self):
		return is_connected(self)