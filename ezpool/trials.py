from functools import wraps

def worker(fun):
	@wraps(fun, assigned=('__name__', '__module__'), updated=())
	def wrapper(*args, **kwargs):
		class Worker(object):
			def __init__(self):
				self._fun = fun

			def run(self, *args, **kwargs):
				return self._fun(*args, **kwargs)
		return Worker().run(*args, **kwargs)
	return wrapper

@worker
def fib(n):
	return n if n<2 else fib(n-1)+fib(n-2)

if __name__ == '__main__':
	a = fib(10)