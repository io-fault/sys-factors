import types
from .. import libconstruct as library
from ...routes import library as libroutes

def test_unix_compiler_collection(test):
	m = {
		'type': 'collection',
	}
	stdhead = [None, '-c', '-v', '-fvisibility=hidden', '-fcolor-diagnostics', '-O3', '-g', '-DFAULT_TYPE=unspecified']
	context = {
		'role': 'optimal',
		'name': 'host',
		'system': {
			'type': None,
		}
	}

	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',), mechanism=m)
	test/cmd == stdhead + ['-o', 'out.o', 'input.c']

	context = {
		'role': 'optimal',
		'name': 'host',
		'system': {
			'source.parameters': [
				('TEST', 'VALUE'),
			],
		}
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',), mechanism=m)
	test/cmd == stdhead + ['-DTEST=VALUE', '-o', 'out.o', 'input.c']

	# coverage flags from metrics role.
	context = {
		'role': 'metrics',
		'name': 'host',
		'system': {
			'source.parameters': [
				('TEST', 'VALUE'),
			],
		}
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',), mechanism=m)
	metrics_head = list(stdhead)
	metrics_head = [None, '-c', '-v', '-fvisibility=hidden', '-fcolor-diagnostics', '-O0', '-g',
		'-fprofile-instr-generate', '-fcoverage-mapping', '-DFAULT_TYPE=unspecified']
	test/cmd == metrics_head + ['-DTEST=VALUE', '-o', 'out.o', 'input.c']

	# include directories
	context = {
		'role': 'optimal',
		'name': 'host',
		'system': {
			'include.directories': [
				'incdir1', 'incdir2',
			],
			'source.parameters': [
				('TEST', 'VALUE'),
			],
		}
	}
	expect = [None, '-c', '-v', '-fvisibility=hidden', '-fcolor-diagnostics', '-O3', '-g',
		'-Iincdir1', '-Iincdir2', '-DFAULT_TYPE=unspecified', '-DTEST=VALUE', '-o', 'out.o', 'input.c']
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',), mechanism=m)
	test/cmd == expect

	# include set
	context = {
		'role': 'optimal',
		'name': 'host',
		'system': {
			'include.set': [
				'inc1.h', 'inc2.h',
			],
		}
	}
	expect = [None, '-c', '-v', '-fvisibility=hidden', '-fcolor-diagnostics', '-O3', '-g',
		'-DFAULT_TYPE=unspecified',
		'-include', 'inc1.h', '-include', 'inc2.h', '-o', 'out.o', 'input.c']
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',), mechanism=m)
	test/cmd == expect

	# injection
	context = {
		'role': 'optimal',
		'name': 'host',
		'system': {
			'command.option.injection': ['-custom-op'],
		}
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',), mechanism=m)
	test/cmd == stdhead + ['-custom-op', '-o', 'out.o', 'input.c']

	# undefines
	context = {
		'role': 'optimal',
		'name': 'host',
		'system': {
			'compiler.preprocessor.undefines': [
				'TEST1', 'TEST2',
			],
		}
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',), mechanism=m)
	test/cmd == stdhead + ['-UTEST1', '-UTEST2', '-o', 'out.o', 'input.c']

	# language
	context = {
		'role': 'optimal',
		'name': 'host',
		'system': {
		}
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',), language='c', mechanism=m)
	test/cmd == stdhead[0:3] + ['-x', 'c'] + stdhead[3:] + ['-o', 'out.o', 'input.c']

	# language and standard
	context = {
		'role': 'optimal',
		'system': {
			'standards': {'c': 'c99'},
		}
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',), language='c', mechanism=m)
	test/cmd == stdhead[0:3] + ['-x', 'c', '-std=c99'] + stdhead[3:] + ['-o', 'out.o', 'input.c']

def test_updated(test):
	import time
	with libroutes.File.temporary() as tr:
		of = tr / 'obj'
		sf = tr / 'src'
		test/library.updated([of], [sf], None) == False

		# object older than source
		of.init('file')
		sf.init('file')
		of.set_last_modified(sf.last_modified().rollback(second=10))
		test/library.updated([of], [sf], None) == False

		of.void()
		of.init('file')
		test/library.updated([of], [sf], None) == True

def test_sequence(test):
	"""
	Check the sequencing of a traversed Sources graph.
	"""
	from .. import libfactor
	m = [
		types.ModuleType("M1"),
		types.ModuleType("M2"),
		types.ModuleType("M3"),
	]
	n = [
		types.ModuleType("N1"),
		types.ModuleType("N2"),
		types.ModuleType("N3"),
	]
	for x in m+n:
		x.__factor_type__ = 'system.library'

	# M1 -> M2
	m[0].m2 = m[1]
	ms = library.sequence(m)
	proc = next(ms)[0]
	test/set(proc) == set((m[1], m[2]))

	proc = ms.send(proc)[0]
	test/set(proc) == set((m[0],))

	# M3 -> N1 -> N2 -> N3
	n[0].n2 = n[1]
	n[1].n3 = n[2]
	m[2].n1 = n[0]
	ms = library.sequence(m+n)
	proc = next(ms)[0]
	test/set(proc) == set([n[2], m[1]])
	test/set(ms.send(())[0]) == set() # no op
	test/set(ms.send([n[2]])[0]) == set((n[1],)) # triggers n[1]
	test/set(ms.send([m[1]])[0]) == set((m[0],)) # triggers m[0]

def test_identity(test):
	import types
	m = types.ModuleType("some.pkg.lib.name")
	m.__factor_type__ = 'system.library'
	test/library.identity(m) == 'name'

	m = types.ModuleType("some.pkg.lib.libname")
	m.__factor_type__ = 'system.library'
	test/library.identity(m) == 'name'

	# executables are indifferent
	m = types.ModuleType("some.pkg.lib.libname")
	m.__factor_type__ = 'system.executable'
	test/library.identity(m) == 'libname'

	# explicit overrides are taken regardless
	m = types.ModuleType("some.pkg.lib.libname")
	m.__factor_type__ = 'system.library'
	m.name = 'libsomethingelse'
	test/library.identity(m) == 'libsomethingelse'

def test_construction_sequence(test):
	"""
	&library.initialize of a temporary system target
	and its subsequent &library.transform and &library.reduce.

	! WARNING:
		Performs no tests aside from execution.
	"""
	import builtins
	from .. import libfactor

	mt = types.ModuleType("pkg.exe", "docstring")
	mt.__factor_type__ = 'system.executable'
	mt.__builtins__ = builtins

	with libroutes.File.temporary() as tr:
		pkgdir = tr / 'pkg' / 'exe'
		py = pkgdir / '__init__.py'
		src = pkgdir / 'src'
		src.init('directory')

		m = src / 'main.c'
		m.init('file')

		mt.__file__ = str(py)
		mt.__package__ = 'pkg.exe'
		mt._init()

		ctx = library.initialize('host', 'host', 'optimal', mt, ())
		xf = list(library.transform(ctx))
		rd = list(library.reduce(ctx))

if __name__ == '__main__':
	from .. import libtest; import sys
	libtest.execute(sys.modules[__name__])
