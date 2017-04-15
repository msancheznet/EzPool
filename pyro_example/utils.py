import os
import Pyro4
from Pyro4.errors import CommunicationError, ConnectionClosedError
from subprocess import Popen, PIPE, STDOUT
from threading import Thread

def is_connected(proxy):
    ''' Check if a Pyro4 proxy is available thorugh the network

            :return bool: True if proxy can communication with remote object
    '''
    try:
        return proxy._pyroBind()
    except (CommunicationError, ConnectionClosedError):
        return False

class CommandExecutor(object):
    def __init__(self, path=os.getcwd(), print_shell=False):
        self._path = path
        self._print = print_shell

    def __del__(self):
        self._p.terminate()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self._p.terminate()

    def __call__(self, *args):
        self._f = Pyro4.Future(self.spawn)
        # self._f(args)

    def spawn(self, *args):
        self._p = Popen(' '.join(*args), stdout=PIPE,
                        stderr=STDOUT, shell=True, cwd=self._path)
        if self._print:
            self._print_output()
        self._p.wait()

    def _print_output(self):
        for line in iter(self._p.stdout.readline, b''):
            print("SHELL:: " + line.decode("utf-8").rstrip())

def new_worker():
    from threading import Thread
    from worker import run_worker, _get_arg_parser
    run_worker(_get_arg_parser().parse_args(['-p 20001']))

if __name__ == '__main__':
    future = Pyro4.Future(new_worker)
    future()
    input("Press Enter to continue...")

    '''cmd = CommandExecutor(print_shell=False)
    cmd(('python', 'scheduler.py','-p','22000'))
    from subprocess import check_call
    check_call('python scheduler.py -p 22000', shell=True)
    raw_input("Press Enter to continue...")'''
