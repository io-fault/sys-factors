"""
# Factor dependency graph checks.
"""
from fault.system import files

def test_sequence(test):
	"""
	# Check the sequencing of a traversed Sources graph.
	"""
	tr = test.exits.enter_context(files.Path.temporary())
	m = [
		types.ModuleType("M0"),
		types.ModuleType("M1"),
		types.ModuleType("M2"),
	]
	n = [
		types.ModuleType("N0"),
		types.ModuleType("N1"),
		types.ModuleType("N2"),
	]
	for x in m+n:
		x.__factor_domain__ = 'system'
		x.__factor_type__ = 'library'
		x.__factor_composite__ = True
		x.__file__ = str(tr / (x.__name__ + '.py'))

	m[0].m1 = m[1]

	factors = [library.Factor(None, x, None) for x in m+n]
	fd = {f.module: f for f in factors}
	ms = library.sequence(factors)
	test/next(ms) == None

	# Initial set: Everything except M1
	proc = ms.send(())[0]
	test/set(x.module for x in proc) == set(n + m[1:])

	proc = ms.send(proc)[0]
	test/set(proc) == set((fd[m[0]],))

	# M2 -> N0 -> N1 -> N2
	n[0].n1 = n[1]
	n[1].n2 = n[2]
	m[2].n0 = n[0]

	# Restart. M0.m1 = M1 still holds.
	factors = [library.Factor(None, x, None) for x in m+n]
	fd = {f.module: f for f in factors}
	ms = library.sequence(factors)
	test/next(ms) == None

	proc = ms.send(())[0]
	# Need exact completion.
	fin = {x.module: x for x in proc}
	test/set(x.module for x in proc) == set((m[1], n[2]))
	test/set(ms.send(())[0]) == set() # no op
	test/set(ms.send(())[0]) == set() # no op
	fn2 = fin[n[2]]
	fm1 = fin[m[1]]

	# triggers n[1]
	test/set(x.module for x in ms.send([fn2])[0]) == set((n[1],))

	# triggers m[0]
	test/set(x.module for x in ms.send([fm1])[0]) == set((m[0],))

if __name__ == '__main__':
	from fault.test import library as libtest; import sys
	libtest.execute(sys.modules[__name__])
