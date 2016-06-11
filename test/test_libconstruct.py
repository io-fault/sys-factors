from .. import libconstruct as library
from ...routes import library as libroutes

def test_unix_compiler_collection(test):
	cc = '/x/realm/bin/clang'
	stdhead = [cc, '-c', '-v', '-fPIC', '-O3', '-g']
	context = {
		'role': 'optimal',
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',))
	test/cmd == [cc, '-c', '-v', '-fPIC', '-O3', '-g', '-o', 'out.o', 'input.c']

	context = {
		'role': 'optimal',
		'compiler.preprocessor.defines': [
			('TEST', 'VALUE'),
		],
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',))
	test/cmd == [cc, '-c', '-v', '-fPIC', '-O3', '-g', '-DTEST=VALUE', '-o', 'out.o', 'input.c']

	# coverage flags from metrics role.
	context = {
		'role': 'metrics',
		'compiler.preprocessor.defines': [
			('TEST', 'VALUE'),
		],
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',))
	metrics_head = [cc, '-c', '-v', '-fPIC', '-O1', '-g']
	test/cmd == metrics_head + ['-fprofile-instr-generate', '-fcoverage-mapping', '-DTEST=VALUE', '-o', 'out.o', 'input.c']

	# include directories
	context = {
		'role': 'optimal',
		'system.include.directories': [
			'incdir1', 'incdir2',
		],
		'compiler.preprocessor.defines': [
			('TEST', 'VALUE'),
		],
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',))
	test/cmd == stdhead + ['-Iincdir1', '-Iincdir2', '-DTEST=VALUE', '-o', 'out.o', 'input.c']

	# include set
	context = {
		'role': 'optimal',
		'include.set': [
			'inc1.h', 'inc2.h',
		],
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',))
	test/cmd == stdhead + ['-include', 'inc1.h', '-include', 'inc2.h', '-o', 'out.o', 'input.c']

	# injection
	context = {
		'role': 'optimal',
		'command.option.injection': ['-custom-op'],
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',))
	test/cmd == stdhead + ['-custom-op', '-o', 'out.o', 'input.c']

	# undefines
	context = {
		'role': 'optimal',
		'compiler.preprocessor.undefines': [
			'TEST1', 'TEST2',
		],
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',))
	test/cmd == stdhead + ['-UTEST1', '-UTEST2', '-o', 'out.o', 'input.c']

	# language
	context = {
		'role': 'optimal',
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',), language='c')
	test/cmd == stdhead[0:3] + ['-x', 'c'] + stdhead[3:] + ['-o', 'out.o', 'input.c']

	# language and standard
	context = {
		'role': 'optimal',
		'standards': {'c': 'c99'},
	}
	cmd = library.unix_compiler_collection(context, 'out.o', ('input.c',), language='c')
	test/cmd == stdhead[0:3] + ['-x', 'c', '-std=c99'] + stdhead[3:] + ['-o', 'out.o', 'input.c']

def test_updated(test):
	import time
	with libroutes.File.temporary() as tr:
		of = tr / 'obj'
		sf = tr / 'src'
		test/library.updated(of, sf, None) == False

		# object older than source
		of.init('file')
		sf.init('file')
		of.set_last_modified(sf.last_modified().rollback(second=10))
		test/library.updated(of, sf, None) == False

		of.void()
		of.init('file')
		test/library.updated(of, sf, None) == True

def test_sequence(test):
	"""
	Check the sequencing of a traversed Sources graph.
	"""
	from .. import libfactor
	m = [
		libfactor.SystemModule("M1"),
		libfactor.SystemModule("M2"),
		libfactor.SystemModule("M3"),
	]
	n = [
		libfactor.SystemModule("N1"),
		libfactor.SystemModule("N2"),
		libfactor.SystemModule("N3"),
	]

	# M1 -> M2
	m[0].m2 = m[1]
	ms = library.sequence(m)
	proc = next(ms)
	test/set(proc) == set((m[1], m[2]))

	proc = ms.send(proc)
	test/set(proc) == set((m[0],))

	# M3 -> N1 -> N2 -> N3
	n[0].n2 = n[1]
	n[1].n3 = n[2]
	m[2].n1 = n[0]
	ms = library.sequence(m+n)
	proc = next(ms)
	test/set(proc) == set([n[2], m[1]])
	test/set(ms.send(())) == set() # no op
	test/set(ms.send([n[2]])) == set((n[1],)) # triggers n[1]
	test/set(ms.send([m[1]])) == set((m[0],)) # triggers m[0]

def test_identity(test):
	import types
	m = types.ModuleType("some.pkg.lib.name")
	m.system_object_type = 'library'
	test/library.identity(m) == 'name'

	m = types.ModuleType("some.pkg.lib.libname")
	m.system_object_type = 'library'
	test/library.identity(m) == 'name'

	# executables are indifferent
	m = types.ModuleType("some.pkg.lib.libname")
	m.system_object_type = 'executable'
	test/library.identity(m) == 'libname'

	# explicit overrides are taken regardless
	m = types.ModuleType("some.pkg.lib.libname")
	m.system_object_type = 'library'
	m.name = 'libsomethingelse'
	test/library.identity(m) == 'libsomethingelse'

def test_construction_sequence(test):
	"""
	&library.initialize of a temporary &libfactor.SystemModule
	and its subsequent &library.transform and &library.reduce.

	! WARNING:
		Performs no tests aside from execution.
	"""
	import builtins
	from .. import libfactor

	mt = libfactor.SystemModule("pkg.exe", "docstring")
	mt.system_object_type = 'executable'
	mt.__type__ = 'system.executable'
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

		ctx = library.initialize('inherit', 'optimal', mt)
		xf = list(library.transform(ctx, 'dynamic'))
		rd = list(library.reduce(ctx))

if __name__ == '__main__':
	from .. import libtest; import sys
	libtest.execute(sys.modules[__name__])
