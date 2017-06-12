# Pull up imports at the package level for convenience
# The user can now say: from ezpool import Pool
from .ezpool import EzPool as Pool
from .worker import run_worker