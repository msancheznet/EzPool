Tutorial
========

Introduction
------------

**EzPool** is a small library that provides the functionality required to run tasks in pools of workers regardless of their physical location. Its **main goal is simplicity** and has been conceived to solve problems such as task serialization, execution and synchronization 

EzPool is written in 100% Python, and builds upon well-known libraries such as ``multiprocessing`` and ``Pyro4``. 

A Quick Example
---------------

Here is a quick example to demonstrate how to use **EzPool** for parallel computing:

.. code-block:: python
	:linenos:

	from ezpool import Pool

	def fib(n):
		return n if n<2 else fib(n-1)+fib(n-2)

	if __name__ == '__main__':
		with Pool() as p:
			results = p.pmap(fun=fib, tasks=range(30), ncpu=2)

You might realize that this is essentially equivalent to the Python's ``multiprocessing's pool`` or the ``concurrent.futures's ProcessPoolExecutor``. Indeed, the syntax is very similar and, under the hood, **EzPool** just wraps the ``multiprocessing`` module in the same way that the ``ProcessPoolExecutor`` does. However, **EzPool** extends these parallel processing capabilities by allowing distributed computing:

.. code-block:: python
	:linenos:

	from ezpool import Pool, BaseWorker

	class FibWorker(BaseWorker):
		def run(self, n):
			return n if n<2 else fib(n-1)+fib(n-2)

	if __name__ == '__main__':
		workers = ('PYRO:worker@localhost:21000','PYRO:worker@localhost:21001')
		with Pool() as p:
			results = p.dmap(fun=FibWorker, tasks=range(30), workers=workers)

As you can see, the code required to work with a parallel or distributed pool is essentially the same with some very minor modifications. For instance, whereas in multiporcessing case you could simply define a function and pass it to the pool, now the function needs to be wrapped around a class and implemented in the ``run`` method. Similarly, the location of workers is passed directly as an argument to the pool following ``Pyro4`` URI naming convention.

Installation
------------

**EzPool** is distributed using the well-known pypi package manager. The easiest way to install it is from the command line using

.. code-block:: python
	
	pip install ezpool

Another option, also from the command line, is to download and decompress **EzPool** into a directory, open a command window and install it into the desired distribution using

.. code-block:: python
	
	python setup.py install

Modes of Operation
==================

**EzPool** contains three modes of operation: Serial, parallel and distributed. They can be utilized through the Pool's ``smap``, ``pmap`` and ``dmap`` functions. In the next sections, I describe the details on how to utilize each of them. 

That being said, and before proceeding to any detailed descriptions, I want to take a moment to show how **EzPool** can be used to run tasks in the three previous modes changing the minimum amount of code. This is useful when you cannot be sure, in advance, of how many jobs will be required (e.g. for testing you could use the serial mode, for medium size problems you could use the parallel, and for really large jobs you could take advantage of multiple computers or even the cloud). 

Consider the following code:

.. code-block:: python
	:linenos:

	import argparse
	from ezpool import EzPool

	def fib(n):
		return n if n<2 else fib(n-1)+fib(n-2)

	class FibWorker(BaseWorker):
		def run(self, n):
			return fib(n)
	
	def get_args_parser():
		""" Add an interface to control the program from a command window """
		parser = argparse.ArgumentParser()
		parser.add_argument('--tasks',  '-t', nargs='?', type=int, default=None)
		parser.add_argument('--mode',   '-m', nargs=1,   type=str, default='serial')
		parser.add_argument('--ncpu,    '-n', nargs=1,   type=int, default=1)
		parser.add_argument('--workers','-w', nargs='?', type=str, default=None)
		return parser

	if __name__ == '__main__':
		# Parse arguments in the command line
		args = get_args_parser().parse_args()

		# Wrap the worker into a class if distributed mode is needed
		fun = FibWorker if args.mode == 'distributed' else fun

		# Run all the tasks
		with Pool(mode=args.mode) as p:
			print p.map(fun=fun, tasks=args.task, ncpu=args.ncpu, workers=args.workers)

If you are familiar with ``Python``'s ``argparse`` module, you know that you can now modify the behavior of the tool during runtime by changing the set of input arguments. For instance, assume that the previous lines of code are saved in a file named *example.py*. Then, from the command line you could do

.. code-block:: python

	python example.py --tasks 1 2 3 4 5

This would compute the five first Fibonacci numbers in serial mode. Observe that not all options are defined. Indeed, in serial mode it does not make sense to define workers. On the other hand, if you wrote

.. code-block:: python

	python example.py --mode parallel --tasks 1 2 3 4 5 --ncpu 2

then the same five Fibonacci numbers would be computed in parallel using two cores. Finally, if you specified


.. code-block:: python

	python example.py --mode distributed --tasks 1 2 3 4 5

then the computation would happen using the distributed mode and off-loading the tasks to a single worker located at ``PYRO:worker@localhost:21000``, which is the default location. You could also say

.. code-block:: python

	python example.py --mode distributed --tasks 1 2 3 4 5 --workers PYRO:worker@localhost:21000 PYRO:worker@localhost:21001

and then two workers would be used, both running in the local machine. Finally, note that simply changing ``localhost`` part of the URI address to another IP address will result in the task being sent over the Internet to a remote machine (as long as that machine is reachable - e.g. no firewalls blocking port 21000 -, and the correct type of worker has been opened previously). 

Serial Mode
-----------

The serial mode of operation is the most basic option that **EzPool** provides. It is essentially a for loop that executes the tasks provided sequentially and returns a dictionary that maps tasks to results. It is provided for convenience and implements some basic functionality such as task execution time monitoring and overall progress reporting.

To use **EzPool** in serial mode, two options are possible: Create a pool with and use the ``smap`` function, or create a pool, specify `mode='serial'` in the constructor and then use the ``map`` function.

**EzPool** silently fails when errors in tasks occur. In particular, instead of raising the respective exception, it's object is returned and stored in the value part of the dictionary. This allows you to quickly identify which sets of input are causing the task to fail. 

Parallel Mode
-------------

Distributed Mode
----------------

EzPool vs. Other Tools
======================