import argparse
import Pyro4
import sys
from copy import copy
from functools import wraps
from threading import Thread, Lock
if sys.version_info >= (3, 0):
	from queue import Queue
else:
	from Queue import Queue
from objects import EzProxy, Closeable, run_object

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
		proxy = EzProxy(uri)
		if not proxy.connected:
			print('Worker {} is not available'.format(uri))
			return

		if not proxy.is_worker:
			Print('Proxy {} is not a compatible worker. You need to subclass Worker'.format(uri))
			return

		print('Worker {} is available'.format(uri))
		self._uris.add(uri)
		Queue._put(self, proxy)

	def __getitem__(self, uri):
		""" Find an item within this queue as indexed by its URI.

			.. Warning:: You should only use this feature from within the DistributedPool
						 along with its *mutex*. Otherwise, this is not thread-safe

			:param str uri: URI of the worker to access
			:return Proxy: Proxy to the worker or None if empty
		"""
		# The queue is empty, so return None
		if self.qsize() == 0:
			return

		# Iterate through the queue grabbing a worker, comparing its URI with the one provided
		# and putting it back if they do not match. Note that this implementation assumes that
		# all workers are equal and therefore their order does not matter
		found = None
		for i in range(self.qsize()):
			p = self.get_nowait()
			if p.uri == uri:
				found = p
				self._uris.remove(uri)
				break
			self.put_nowait(p)
		return found

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
		""" Return true if the queue is not empty """
		return not self.empty()


@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class DistributedPool(Closeable):
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
	def __init__(self, daemon):
		Closeable.__init__(self, daemon)

		'''Initialize the pool.'''
		self._idle = WorkerQueue()
		self._running = {}
		self._results = {}

		# The mutex must be held to change the pool of workers
		self._mutex = Lock()

		# Indicate that this pool has been shutdown
		self._shut = False

	@property
	def workers(self):
		'''	Get workers available in this pool '''
		uris = copy(self._idle._uris)
		uris.update(self._running.keys())	# In reality this is not necessary, no one takes URIs out of _idle queue
		return set(uris)

	def add_worker(self, uri):
		''' Add a worker through its URI. If it already present in the pool, ignore. 

				:param str uri: The URI of the worker to register
		'''
		with self._mutex:
			if uri not in self.workers:
				self._idle.add(uri)

	def close_worker(self, uri):
		""" Close a worker in this pool.

			.. Tip:: This function is thread-safe, so use it for your operations

			:param str URI: Worker to close
		"""
		with self._mutex:
			self._close_worker(uri)

	def _close_worker(self, uri):
		""" Close the worker identified by the passed URI
 			
 			:param str URI: Worker to close
		"""
		if uri in self._running:
			# If worker is running, it can be accessed directly
			print('WARNING: Worker {} is shutting down while still processing a job'.format(uri))
			proxy = self._running.pop(uri)
			self._shutdown_proxy(proxy)
		else:
			# Get proxy from the idle queue of workers
			proxy = self._idle[uri]
			self._shutdown_proxy(proxy)

		print('Worker {} has been closed'.format(uri))

	def shutdown(self):
		""" Shutdown the pool and all its workers """
		with self._mutex:
			for uri in self.workers:
				self._close_worker(uri)
			self._shut = True

	def _shutdown_proxy(self, proxy):
		""" Shutdown a proxy and release the connection 
			
			.. Warning:: You should only call this function with you have the mutex
		"""
		if proxy is None:
			print('Worker {} is not present in the pool'.format(uri))
			return
		proxy.shutdown()
		proxy._pyroRelease()
		del proxy

	def __contains__(self, uri):
		''' Check if the worker identified by this URI is already in the pool

				:param str uri: The worker URI
				:param bool: True if the worker is already in the pool
		'''
		return (uri in self.workers)

	def __len__(self):
		""" Return the number of workers available """
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
			# Acquire the mutex so that you cannot add/delete worker while you
			# are using it here
			with self._mutex:
				# If this pool is shut, do not submit any more tasks
				if self._shut:
					break

				# Get the next available worker. If all of them are busy, block for
				# now
				worker = self._idle.get(block=True)
				wrk_id = worker.uri

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
		# Get the worker that will perform the task. If not present, this means that another
		# concurrent task deleted it.
		worker = self._running.get(wrk_id, None)
		if worker is None:
			self._results[task] = 'Worker was unavailable at evaluation time'
			return

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

def _get_args_parser():
	'''	Create the argument parser that defines the set of options available to configure
			a distributed pool

			.. Tip:: To see options available, locate this file in a command shell and execute `python distributed_pool.py -h`
	'''
	parser = argparse.ArgumentParser()
	parser.add_argument('--address', '-a', nargs='?',default='localhost', help='IP adress', type=str)
	parser.add_argument('--port', '-p', nargs='?',default=21000, help='TCP port', type=int)
	parser.add_argument('--name', '-n', nargs='?',default='pool', help='Distributed pool name', type=str)
	parser.add_argument('--msg','-m', nargs='?', default='Distributed pool ready to proces jobs:', help='Message to display when object is started', type=str)
	#parser.add_argument('--nserver', '-ns',action='store_true', help='Run with name server')
	return parser

if __name__ == '__main__':
	run_object(DistributedPool, _get_args_parser().parse_args())
