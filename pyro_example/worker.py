import Pyro4
import argparse

def fib(n):
	return 1 if n<2 else fib(n-1)+fib(n-2)

@Pyro4.expose
class Worker(object):
	def run(self,n):
		result = fib(n)
		print(result)
		return result

def run_worker(args):
	Pyro4.Daemon.serveSimple({Worker:args.name}, host=args.address, 
							 port=args.port, ns=args.nserver)

def _get_arg_parser():
	parser = argparse.ArgumentParser()
	parser.add_argument('--address','-a', nargs='?', default='localhost', help='IP adress', type=str)
	parser.add_argument('--port','-p', nargs='?', default=20000, help='TCP port', type=int)
	parser.add_argument('--name','-n', nargs='?', default='worker', help='Worker name', type=str)
	parser.add_argument('--nserver','-ns', action='store_true', help='Run name server')
	return parser

if __name__ == '__main__':
	run_worker(_get_arg_parser().parse_args())