import itertools
import collections
from .. import tracing as module

class RandomClass(object):
	def rc_method(self):
		i = 7
		k = i + 2
		return k

	def outer_method(self):
		k = 1
		k += 2
		self.rc_method()

	@classmethod
	def generate(Class):
		i = Class()
		i.rc_method()
		i.outer_method()
		i.rc_method()

def traced_call(C):
	C.subscribe()

	rc = RandomClass()
	rc.rc_method()
	rc.outer_method()
	rc.rc_method()

	C.cancel()

def test_Collector(test):
	"""
	# Exercise basic functionality by simulating events.
	"""

	cd = list()
	ch = itertools.count()
	CC = module.instr.Collector(cd.append, ch.__next__)

	pd = list()
	ph = itertools.count()
	PC = module.Collector(pd.append, ph.__next__)

	traced_call(CC); traced_call(PC)

	test/pd != []
	test/cd != []

events = [
	(('test/test_tracing.py', 22, 30, 'test_collection'), 2, 0),
	(('test/test_tracing.py', 22, 31, 'test_collection'), 2, 1),
	(('test/test_tracing.py', 8, 8, 'rc_method'), 0, 2),
	(('test/test_tracing.py', 8, 9, 'rc_method'), 2, 3),
	(('test/test_tracing.py', 8, 10, 'rc_method'), 2, 4),
	(('test/test_tracing.py', 8, 11, 'rc_method'), 2, 5),
	(('test/test_tracing.py', 8, 11, 'rc_method'), 3, 6),
	(('test/test_tracing.py', 22, 32, 'test_collection'), 2, 7),
	(('test/test_tracing.py', 13, 13, 'outer_method'), 0, 8),
	(('test/test_tracing.py', 13, 14, 'outer_method'), 2, 9),
	(('test/test_tracing.py', 13, 15, 'outer_method'), 2, 10),
	(('test/test_tracing.py', 13, 16, 'outer_method'), 2, 11),
	(('test/test_tracing.py', 8, 8, 'rc_method'), 0, 12),
	(('test/test_tracing.py', 8, 9, 'rc_method'), 2, 13),
	(('test/test_tracing.py', 8, 10, 'rc_method'), 2, 14),
	(('test/test_tracing.py', 8, 11, 'rc_method'), 2, 15),
	(('test/test_tracing.py', 8, 11, 'rc_method'), 3, 16),
	(('test/test_tracing.py', 13, 16, 'outer_method'), 3, 17),
	(('test/test_tracing.py', 22, 34, 'test_collection'), 2, 18,),

	(('test/test_tracing.py', 8, 8, 'rc_method'), 0, 19),
	(('test/test_tracing.py', 8, 9, 'rc_method'), 2, 20),
	(('test/test_tracing.py', 8, 10, 'rc_method'), 2, 21),
	(('test/test_tracing.py', 8, 11, 'rc_method'), 2, 22),
	(('test/test_tracing.py', 8, 11, 'rc_method'), 3, 23),
	(('test/test_tracing.py', 22, 32, 'test_collection'), 2, 24),
]

if __name__ == '__main__':
	from .. import libtest; import sys
	libtest.execute(sys.modules[__name__])
