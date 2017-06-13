from ezproxy import EzProxy, connect_to
from objects import run_object, spawn_object
from scheduler import _get_args_parser, JobManager
from utils import LogFun
from collections import defaultdict
import multiprocessing as mp

from worker import fib, build_worker, FibWorker

class EzPool(object):
	""" This class provides an unique interface to run a set of tasks in serial, parallel or
		distributed mode. To run tasks in through this Pool, use the ``map`` function.

		**Serial Mode**: All tasks are run in order in one core:
		
		.. code-block:: python
			:linenos:

			def echo(task):
				return task

			tasks = list(range(30))
			with Pool() as pool:
				results = pool.map_serial(echo, tasks)

		**Parallel Mode**:All tasks are run in multiple cores of one machine (no order is preserved):

		.. code-block:: python
			:linenos:

			def echo(task):
				return task

			tasks = list(range(30))
			with Pool() as pool:
				results = pool.map_parallel(echo, tasks, ncores=5)

		**Distributed Mode**:All tasks are run in multiple cores of one or multiple machines (no order is preserved):

		.. code-block:: python
			:linenos:

			from ezpool.workers import EchoWorker

			tasks   = list(range(30))
			workers = ('PYRO:worker@localhost:21000', 'PYRO:worker@remote:21000')
			worker_type = EchoWorker
			with Pool() as pool:
				results = pool.map_distributed(tasks, workers=workers, worker_type=worker_type)

		The distributed mode relies on the JobManager object to schedule tasks across workers. In
		general, you will run the JobManager on your local machine, but that is not required. Also,
		the JobManager is set up so that you can add/remove workers while computations are going on,
		but removing a worker that is currently running a task will result in that task not being
		evaluated.

		.. Tip:: The `map` function of this pool is blocking, i.e. the current thread will wait until
				 all the results are available before proceeding.
		.. Tip:: You could use the distributed mode and have the Job Manager and the workers live in
				 the localhost. This would essentially be equivalent to the `parallel` mode, but will
				 incur in more overhead, so it is not recommended.
		.. Tip:: For testing purposes, you can use the distributed mode without any parameters for the
				 `map` function. This will just spawn new processes in the local machine for the job manager
				 and workers, and clean them after the jobs have been run.
	"""
	def __init__(self, mode=None):
		self._mode  = mode
		self._procs = {}

	def __enter__(self):
		""" Return the pool object when entering a ``with`` statement """
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		""" Before exiting a ``with`` block, shutdown the pool and all the workers

			:param exc_type: Type of exception raised within the ``with`` statement
			:param exc_val: Exception value
			:param exc_tb: Exception traceback

			.. Warning:: If an exception occurs within the ``with`` block, it will be raised
						 in the calling thread after exiting and shutting everything down.
		"""
		self.shutdown()
		return False    # Reraise the exception

	def shutdown(self):
		""" Shutdown the pool by shutting down the job manager and the workers """
		for uri in self._procs:
			proxy = EzProxy(uri)
			if proxy.connected:
				proxy.shutdown()
				proxy.close()
			self._procs[uri].terminate()
		self._procs.clear()

	def map(*args, **kwargs):
		""" Wrapper for ``smap``, ``pmap``, ``dmap`` so that you can programmatically
			use the right type of pool by setting the attribute ``mode``. The arguments
			of the function must be the same as those in ``smap``, ``pmap``, ``dmap``
			respectively

			.. code-block:: python
				:linenos:

				from ezpool import Pool

				with Pool(mode='parallel') as p:
					res = p.map(fun, range(30), ncpu=2)
		"""
		d = defaultdict()
		d.update(kwargs)

		if self._mode is 'serial':
			sargs = ['fun','tasks','msg']
			kwargs = dict([(a,D.get(a)) for a in sargs if D.get(a) is not None])
			return self.smap(**kwargs)
		elif self._mode is 'parallel':
			pargs = ['fun','tasks','ncpu','msg']
			kwargs = dict([(a,D.get(a)) for a in pargs if D.get(a) is not None])
			return self.pmap(**kwargs)
		elif self._mode is 'distributed':
			dargs = ['fun','tasks','job_mgr','workers']
			kwargs = dict([(a,D.get(a)) for a in dargs if D.get(a) is not None])
			return self.dmap(**kwargs)
		else:
			raise ValueError("map can only be used if the pool has mode 'serial', 'parallel', 'distributed'. Otherwise, use smap, pmap, dmap")

	def smap(self, fun=None, tasks=None, msg='Computation process'):
		""" Run tasks in serial mode 
			
			:param func fun: Function to run for each task
			:param list tasks: List of tasks to complete. Arguments for each task should
							   be passed as a list of tuples, each tuple ordered according
							   to the arguments of ``fun``
			:param str msg: Message to display at one reporting progress

			:return dict: Keys are tasks, values are results
		"""
		# Initialize variables
		results, N = [], len(tasks)

		# Submit the tasks
		for i, task in enumerate(tasks):
			# Create a tuple from the task to later unpack. 
			task = self._wrap_task(task)

			# Run and time the task
			res, telapsed = LogFun(fun)(*task)

			# Display progress
			show_progress(task, res, i, N, telapsed, msg=msg)

			# Save the result
			results.append(res)

		return dict(zip(tasks, results))

	def pmap(self, fun=None, tasks=None, ncpu=1, msg='Computation process'):
		""" Run tasks in parallel mode 

			:param func fun: Function to run for each task
			:param list tasks: List of tasks to complete. Arguments for each task should
							   be passed as a list of tuples, each tuple ordered according
							   to the arguments of ``fun``

			:return dict: Keys are tasks, values are results
		"""
		# Initialize variables
		results, N = [], len(tasks)
		maxcpu = max(mp.cpu_count() - 1, 1)
		ncores = min(ncpu, N, maxcpu)
		pool   = mp.Pool(ncores)

		# Submit the jobs
		futures = [pool.apply_async(LogFun(fun), args=self._wrap_task(task)) for task in tasks]

		# Get the results
		for i, (task, future) in enumerate(zip(tasks,futures)):
			# Wait until available
			res, telapsed = future.get()

			# Display progress
			show_progress(task, res, i, N, telapsed, msg=msg)

			# Save the result
			results.append(res)

		# Clean pool
		pool.close()
		pool.join()

		return dict(zip(tasks, results))

	def dmap(self, fun=None, tasks=None, job_mgr='PYRO:jobmgr@localhost:20000', workers=('PYRO:worker@localhost:21000',)):
		""" Run tasks in distributed mode 

			:param list tasks: List of tasks to complete. Arguments for each task should
							   be passed as a list of tuples, each tuple ordered according
							   to the arguments of ``fun``
			:param job_mgr: URI for the job manager (default is 'PYRO:jobmgr@localhost:20000')
			:param list workers: URIs for the workers (default is ['PYRO:worker@localhost:21000'])
			:param class fun: Type of worker to run tasks (default is ezpool.workers.EchoWorker)
		"""
		try:
			# Connect to the job manager (or create a local one if necessary)
			job_mgr_p = self._new_proxy(job_mgr, JobManager)
			
			# Add each worker to the job manager (before adding, they can be automatically created if need be)
			for worker in workers:
				worker_p = self._new_proxy(worker, fun)
				job_mgr_p.add_worker(worker)
				worker_p.close()
		except Exception as e:
			# Shut the pool down before leaving
			self.shutdown()
			raise e

		# Submit the jobs to the job manager and get the results (this call blocks)
		res = job_mgr_p.map(tasks)
		job_mgr_p.close()

		return res

	def _new_proxy(self, uri, obj_type=None):
		""" Get a new proxy for the provided URI. If the URI is not available and its supposed
			to be run locally, a new process will be automatically spawned

			:param str URI: The URI to get a proxy to
			:parma object obj_type: The type of object that should be opened if you cannot connect to it (default is ``None``)

			.. Tip:: In most cases, you do not need to provide the obj_type since the worker should
					 be already available.
		"""
		proxy, proc = connect_to(uri, obj_type)
		if proc is not None:
			self._procs[uri] = proc
		return proxy

	def _wrap_task(self, task):
		""" Wrap task into a tuple 

			:param object task
			:return tuple: Wrapped task
		"""
		return tuple(task) if hasattr(task, '__iter__') else (task,)

def show_progress(task, result, i, N, t, msg='Computation process'):
	""" Print a statement to report progress in the pool
		
		:param object task: The task
		:param object result: The result object. If it is an exception, then flag error
		:param integer i: Index for this task
		:param integer N: Total number of tasks
		:param str msg: Message to display at the beginning
	"""
	if isinstance(result, Exception):
		print('{} for {} failed. ERROR: {}'.format(msg, task, result))
	else:
		print('{} ({}/{} - {:0.1f}%) - Elapsed time {}...\t\tSUCESS'.format(msg, i+1, N, 100*(1.0*(i+1)/N), t))

if __name__ == '__main__':

	

	workers = ('PYRO:worker@localhost:21000','PYRO:worker@localhost:21001')
	with EzPool() as p:
		res1 = p.pmap(fun=fib, tasks=range(35), ncpu=2)
		res2 = p.dmap(fun=FibWorker, tasks=range(35), workers=workers)
		#res2 = p.dmap(range(30), workers=workers, fun=build_worker(fib))
	print(res1)
	print(res2)