import Pyro4
import argparse
from objects import Worker, run_object

def fib(n):
	return 1 if n<2 else fib(n-1)+fib(n-2)

@Pyro4.expose
class FibWorker(Worker):
	def run(self,n):
		result = fib(n)
		print(result)
		return result

def _get_args_parser():
	parser = argparse.ArgumentParser()
	parser.add_argument('--address','-a', nargs='?', default='localhost', help='IP adress', type=str)
	parser.add_argument('--port','-p', nargs='?', default=20000, help='TCP port', type=int)
	parser.add_argument('--name','-n', nargs='?', default='worker', help='Worker name', type=str)
	parser.add_argument('--msg','-m', nargs='?', default='Worker ready to proces jobs:', help='Message to display when object is started', type=str)
	#parser.add_argument('--nserver','-ns', action='store_true', help='Run name server')
	return parser

if __name__ == '__main__':
	run_object(FibWorker, _get_args_parser().parse_args())