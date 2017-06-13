import Pyro4
import Pyro4.util
import pytest
import sys
from ezproxy import EzProxy

sys.excepthook = Pyro4.util.excepthook

@pytest.fixture
def pool():
	pool = EzProxy('PYRO:jobmgr@localhost:21000')
	pool.add_worker('PYRO:worker@localhost:20000')
	pool.add_worker('PYRO:worker@localhost:20001')
	pool.add_worker('PYRO:worker@localhost:20002')
	return pool

@pytest.fixture
def empty_pool():
	pool = EzProxy('PYRO:jobmgr@localhost:21001')
	return pool

def test_distributed_pool_ok(pool):
	inputs = list(range(30))
	results = [1,1,2,3,5,8,13,21,34,55,89,144,233,377,610,987,
				1597,2584,4181,6765,10946,17711,28657,46368,75025,
				121393,196418,317811,514229,832040]

	# Submit jobs
	outputs = pool.map(inputs)

	# Perform test
	for i in inputs:
		assert outputs[i] == results[i]

def test_distributed_pool_error(pool):
	inputs  = [1, 'hi']
	outputs = pool.map(inputs)
	assert len(outputs) == 2

def test_empty_pool_error(empty_pool):
	with pytest.raises(RuntimeError):
		empty_pool.map([1])

if __name__ == '__main__':
	pytest.main(['testing.py'])