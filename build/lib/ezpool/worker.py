import abc
import argparse
import Pyro4
import six
import sys
from objects import run_object, Closeable

def fib(n):
	return 1 if n<2 else fib(n-1)+fib(n-2)

@Pyro4.expose
@six.add_metaclass(abc.ABCMeta)
class BaseWorker(Closeable):
	""" Define an abstract class Worker that enforces everyone
		implementing the ``run`` and ``is_worker`` method.
	"""
	@abc.abstractmethod
	def run(self):
		""" Method called during the JobManager execution """
		pass

	@property
	def is_worker(self):
		""" Return true since this is a worker """
		return True

	@staticmethod
	def parse_args(args=None):
		return _get_args_parser().parse_args(args)

def build_worker(object):
	@Pyro4.expose
	class Worker(BaseWorker):
		__name__ = 'Worker'

		def __init__(self, daemon):
			Closeable.__init__(self, daemon)
			self._fun = fun

		def run(self, *args, **kwargs):
			return self._fun(*args, **kwargs)
	return Worker

class EchoWorker(BaseWorker):
	""" A simple worker that just echoes back the input it receives """
	def run(self, inp):
		return inp
		
def _get_args_parser():
	parser = argparse.ArgumentParser()
	parser.add_argument('--uri', '-u', nargs='?', default='', help='Job manager URI', type=str)
	parser.add_argument('--address','-a', nargs='?', default='localhost', help='IP adress', type=str)
	parser.add_argument('--port','-p', nargs='?', default=21000, help='TCP port', type=int)
	parser.add_argument('--name','-n', nargs='?', default='worker', help='Worker name', type=str)
	parser.add_argument('--msg','-m', nargs='?', default='Worker ready to proces jobs:', help='Message to display when object is started', type=str)
	#parser.add_argument('--nserver','-ns', action='store_true', help='Run name server')
	return parser

def run_worker(obj, args=None):
	""" Run a worker. If ``obj`` is a function, wrap it around a ``Worker`` class

		:param class cls: Class that will be run as a Pyro object in a deamon
		:param args: Arguements to parse by the object
	"""
	# If obj is a plain python function, wrap it around a generic worker
	# class that calls it when ``run`` is called from the Job Manager.
	if callable(obj) and getattr(obj, "run", None) is None:
		obj = build_worker(obj)

	# Run the worker
	run_object(obj, args)

if __name__ == '__main__':
	run_worker(fib)