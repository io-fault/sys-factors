"""
# Factor dependency graph checks.
"""
from fault.system import files

def test_sequence(test):
	"""
	# Check the sequencing of a traversed Sources graph.
	"""
	test.skip("not implemented")

if __name__ == '__main__':
	from fault.test import library as libtest; import sys
	libtest.execute(sys.modules[__name__])
