import argparse
import Pyro4
import sys
from copy import copy
from functools import wraps
from threading import Thread
if sys.version_info >= (3, 0):
	from queue import Queue
else:
	from Queue import Queue
from objects import EzProxy

class WorkerQueue(Queue):
	''' Subclass Python's native queue to work with Pyro's proxys. `WorkerQueue`
			combines a traditional Queue with a Set to facilitate operations that
			check if a connection with a worker is already present in the system.
	'''

	def _init(self, maxsize):
		''' Initialize the Queue. Use the `_init` function as indicated in Python's 
				documentation

				:param int maxsize: Max size for the queue
		'''
		Queue._init(self, maxsize)
		self._uris = set()

	def add(self, uri):
		''' Add a worker to the queue through its URI

				:param str uri: A fully formed URI address
		'''
		print('Hola')
		proxy = EzProxy(uri)
		if not proxy.connected:
			print('Worker {} is not available'.format(uri))
			return
		print('Hola2')

		if not proxy.is_worker:
			Print('Proxy {} is not a compatible worker. You need to subclass Worker'.format(uri))
			return
		print('Hola3')

		print('Worker {} is available'.format(uri))
		self._uris.add(uri)
		Queue._put(self, proxy)
		print('Hola4')

	def __contains__(self, uri):
		""" Reimplement the `contains` operation to check if a given
				worker identified by a given URI is already in the queue

				:param str uri: The URI to check
		"""
		return uri in self._uris

	def __len__(self):
		""" Return the number of workers available """
		return self.qsize()

	def __bool__(self):
		return not self.empty()


@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class DistributedPool(object):
	''' Distributed pool of workers analogous to Python's multiprocessing Pool.

			:ivar WorkerQueue _idle: Queue with idle workers
			:ivar dict _running: Dictionary that maps URIs with busy workers
			:ivar dict _result: Dictionary that maps tasks to its results

			To run this distributed pool simply run this file as a script

			To work with the pool from another process, use the following template:

			.. code-block:: Python

					pool = EzProxy('PYRO:pool@localhost:21000')	
					pool.register_worker('PYRO:worker@localhost:20000')
					pool.register_worker('PYRO:worker@localhost:20001')

					results = pool.map(inputs)

			Workers of this pool can be any exposed Pyro4 class that contain a `run` method. This
			is called internally be the pool. The following code snippet demonstrates how to build
			a worker:

			.. code-block:: Python

					import Pyro4

					@Pyro4.expose
					class Worker(object):
							def run(self,n):
									result = fib(n)
									print(result)
									return result

					if __name__ == '__main__':
							Pyro4.Daemon.serveSimple({Worker:'worker'}, host='localhost', port=20000, ns=False)

			.. Warning:: For the previous example to work, a pool and two workers must be opened 
									 in separate processes (e.g. separate command windows)
			.. Warning:: The `map` function is implemented using threads. The number of threads 
									 concurrently running is equal to `min(# tasks, # workers)`, so this
									 sets a limitation in the number of tasks that the pool can support
	'''

	def __init__(self):
		'''Initialize the pool.'''
		self._idle = WorkerQueue()
		self._running = {}
		self._results = {}

	@property
	def _workers(self):
		'''	Get workers available in this pool '''
		uris = copy(self._idle._uris)
		uris.update(self._running.keys())
		return set(uris)

	def add_worker(self, uri):
		''' Add a worker through its URI. If it already present in the pool, ignore. 

				:param str uri: The URI of the worker to register
		'''
		if uri not in self._workers:
			self._idle.add(uri)

	def __contains__(self, uri):
		''' Check if the worker identified by this URI is already in the pool

				:param str uri: The worker URI
				:param bool: True if the worker is already in the pool
		'''
		return (uri in self._workers)

	def __len__(self):
		return len(self._idle) + len(self._running)

	def map(self, tasks):
		'''	Run a set of tasks in this pool. The tasks will be distributed across all workers
				in the distributed system, and the function will block the main thread until all
				results are available for collecting them.

				:param list tasks: List containing the inputs for each function evaluation.

				.. Tip:: If the function evaluated by the distributed system has more than one input,
								 pass a list of tuples, one per task to be run
				.. Warning:: The current `map` implementation does not support keyword arguments
		'''
		# Check if there are any workers available
		if not self._idle:
			raise RuntimeError('No workers available')

		# Initialize variables
		self._results.clear()
		threads = []

		# Submit the tasks, running each of them in a separate thread
		for task in tasks:
			# Get the next available worker. If all of them are busy, block for
			# now
			worker = self._idle.get(block=True)
			wrk_id = worker._pyroUri.asString()

			# Initialize the thread and mark this worker as running
			# Note: Do not start the thread before putting it into _running to
			# prevent concurrency problems
			thread = Thread(target=self._run_task, args=(wrk_id, task))
			threads.append(thread)
			self._running[wrk_id] = worker
			thread.start()

		# Wait for all the threads that monitor workers to finish. This ensures that
		# all results are available when we return from this function
		for thread in threads:
			thread.join()

		return self._results

	def _run_task(self, wrk_id, task):
		''' Run a task by calling the `run` method in the worker. Note that this function
				is called always from a separate thread.

				:param str wrk_id: Worker URI that will run the task
				:param tuple task: Tuple with the inputs for the `run` function in the workers, properly ordered
		'''
		# Get the worker that will perform the task
		worker = self._running[wrk_id]

		# Wrap the task with a try catch to silently fail if something goes wrong in the worker.
		# The user will see that, for a given task, the map has returned an
		# Exception
		try:
			result = worker.run(task)
		except Exception as err:
			result = err
		self._results[task] = result

		# Put this worker back in the idle queue. Doing this in a separate thread ensures
		# that the pool thread does not get indefinitely blocked waiting for a worker to become
		# available
		self._idle.put_nowait(worker)


def run_pool(args):
	'''	Run the distributed pool as a basic Pyro4 server

			:param ArgumentParser args: Set of arguments parsed

			.. Tip:: The native Python argument parser is used to standardize the inputs
	'''
	Pyro4.Daemon.serveSimple({DistributedPool: args.name}, host=args.address,
							 port=args.port, ns=args.nserver)


def _get_arg_parser():
	'''	Create the argument parser that defines the set of options available to configure
			a distributed pool

			.. Tip:: To see options available, locate this file in a command shell and execute `python distributed_pool.py -h`
	'''
	parser = argparse.ArgumentParser()
	parser.add_argument('--address', '-a', nargs='?',
						default='localhost', help='IP adress', type=str)
	parser.add_argument('--port', '-p', nargs='?',
						default=21000, help='TCP port', type=int)
	parser.add_argument('--name', '-n', nargs='?',
						default='pool', help='Distributed pool name', type=str)
	parser.add_argument('--nserver', '-ns',
						action='store_true', help='Run with name server')
	return parser

if __name__ == '__main__':
	run_pool(_get_arg_parser().parse_args())
