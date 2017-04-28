import os.path
import types
from .. import library
from ...routes import library as libroutes

def test_Factor(test):
	"""
	# Check the Construction Factor features.
	"""
	f = library.Factor.from_fullname(__name__)
	test.isinstance(f.module, types.ModuleType)
	test.isinstance(f.route, libroutes.Import)
	test.isinstance(f.module_file, libroutes.File)

	# Check cache directory.
	pkgdir = os.path.dirname(__file__)
	pkgcache = os.path.join(pkgdir, '__pycache__')
	test/str(f.cache_directory) == pkgcache

	# Defaults.
	test/f.type == 'python'
	test/f.dynamics == 'library'
	test/str(f.source_directory) == str(pkgdir)

	fpir = os.path.join(pkgcache, library.Factor.default_fpi_name)
	test/str(f.fpi_root) == str(fpir)

def test_unix_compiler_collection(test):
	"""
	# Check &.library.unix_compiler_collection constructions.

	# Originally written for an older API, the current incarnation
	# tries to adapt the old parameter style to the new giving the
	# test some unnecessary confusion.
	"""
	import types
	Build = library.Build
	Factor = library.Factor

	cc_function = library.unix_compiler_collection
	m = {
		'type': 'collection',
	}
	adapter = {
		'language': 'c',
	}
	def cc(ctx, outfile, inputs, mechanism=m, language=None):
		fm = types.ModuleType("__imaginary__")
		fm.__file__ = '/dev/null'
		f = Factor.from_module(fm)
		adapter = {}
		bp = ctx['system'].get('source.parameters') or []
		bp.extend([(k,None) for k in ctx['system'].get('compiler.preprocessor.undefines', ())])
		refs = ctx['system'].get('refs', {})
		opts = ctx['system'].get('command.option.injection', ())
		include_set = ctx['system'].get('include.set', ())
		if 'standards' in ctx['system']:
			fm.standards = ctx['system']['standards']
		b = Build((ctx, mechanism, f, refs, {}, ctx['variants'], None, bp))
		return cc_function(b, adapter, None, outfile, language, inputs, options=opts, includes=include_set)

	stdhead = [None, '-c', '-v', '-fvisibility=hidden', '-fcolor-diagnostics', '-O3', '-g']
	context = {
		'variants': {'purpose':'optimal', 'name':'host'},
		'system': {
			'type': None,
		}
	}

	cmd = cc(context, 'out.o', ('input.c',), mechanism=m)
	test/cmd == stdhead + ['-o', 'out.o', 'input.c']

	context = {
		'variants': {'purpose':'optimal', 'name':'host'},
		'system': {
			'source.parameters': [
				('TEST', 'VALUE'),
			],
		}
	}
	cmd = cc(context, 'out.o', ('input.c',), mechanism=m)
	test/cmd == stdhead + ['-DTEST=VALUE', '-o', 'out.o', 'input.c']

	# coverage flags from metrics role.
	context = {
		'variants': {'purpose':'metrics', 'name':'host'},
		'system': {
			'source.parameters': [
				('TEST', 'VALUE'),
			],
		}
	}
	cmd = cc(context, 'out.o', ('input.c',), mechanism=m)
	metrics_head = list(stdhead)
	metrics_head = [None, '-c', '-v', '-fvisibility=hidden', '-fcolor-diagnostics', '-O0', '-g',
		'-fprofile-instr-generate', '-fcoverage-mapping']
	test/cmd == metrics_head + ['-DTEST=VALUE', '-o', 'out.o', 'input.c']

	# include directories
	context = {
		'variants': {'purpose':'optimal', 'name':'host'},
		'system': {
			'refs': {
				('source', 'library'): [
					library.iFactor.headers(x) for x in [
						'incdir1', 'incdir2',
					]
				]
			},
			'source.parameters': [
				('TEST', 'VALUE'),
			],
		}
	}
	expect = [None, '-c', '-v', '-fvisibility=hidden', '-fcolor-diagnostics', '-O3', '-g',
		'-Iincdir1', '-Iincdir2', '-DTEST=VALUE', '-o', 'out.o', 'input.c']
	cmd = cc(context, 'out.o', ('input.c',), mechanism=m)
	test/cmd == expect

	# include set
	context = {
		'variants': {'purpose':'optimal', 'name':'host'},
		'system': {
			'include.set': [
				'inc1.h', 'inc2.h',
			],
		}
	}
	expect = [None, '-c', '-v', '-fvisibility=hidden', '-fcolor-diagnostics', '-O3', '-g',
		'-include', 'inc1.h', '-include', 'inc2.h', '-o', 'out.o', 'input.c']
	cmd = cc(context, 'out.o', ('input.c',), mechanism=m)
	test/cmd == expect

	# injection
	context = {
		'variants': {'purpose':'optimal', 'name':'host'},
		'system': {
			'command.option.injection': ['-custom-op'],
		}
	}
	cmd = cc(context, 'out.o', ('input.c',), mechanism=m)
	test/cmd == stdhead + ['-custom-op', '-o', 'out.o', 'input.c']

	# undefines
	context = {
		'variants': {'purpose':'optimal', 'name':'host'},
		'system': {
			'compiler.preprocessor.undefines': [
				'TEST1', 'TEST2',
			],
		}
	}
	cmd = cc(context, 'out.o', ('input.c',), mechanism=m)
	test/cmd == stdhead + ['-UTEST1', '-UTEST2', '-o', 'out.o', 'input.c']

	# language
	context = {
		'variants': {'purpose':'optimal', 'name':'host'},
		'system': {
		}
	}
	cmd = cc(context, 'out.o', ('input.c',), mechanism=m, language='c')
	test/cmd == stdhead[0:3] + ['-x', 'c'] + stdhead[3:] + ['-o', 'out.o', 'input.c']

	# language and standard
	context = {
		'variants': {'purpose':'optimal', 'name':'host'},
		'system': {
			'standards': {'c': 'c99'},
		}
	}
	cmd = cc(context, 'out.o', ('input.c',), language='c', mechanism=m)
	test/cmd == stdhead[0:3] + ['-x', 'c', '-std=c99'] + stdhead[3:] + ['-o', 'out.o', 'input.c']

def test_updated(test):
	tr = test.exits.enter_context(libroutes.File.temporary())

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
	of.set_last_modified(sf.last_modified().elapse(second=10))
	test/library.updated([of], [sf], None) == True

def test_sequence(test):
	"""
	# Check the sequencing of a traversed Sources graph.
	"""
	tr = test.exits.enter_context(libroutes.File.temporary())
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
		x.__factor_type__ = 'system'
		x.__factor_dynamics__ = 'library'
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

def test_identity(test):
	import types
	m = types.ModuleType("some.pkg.lib.name")
	m.__factor_type__ = 'system'
	m.__factor_dynamics__ = 'library'
	test/library.identity(m) == 'name'

	m = types.ModuleType("some.pkg.lib.libname")
	m.__factor_type__ = 'system'
	m.__factor_dynamics__ = 'library'
	test/library.identity(m) == 'name'

	# executables are indifferent
	m = types.ModuleType("some.pkg.lib.libname")
	m.__factor_type__ = 'system'
	m.__factor_dynamics__ = 'executable'
	test/library.identity(m) == 'libname'

	# explicit overrides are taken regardless
	m = types.ModuleType("some.pkg.lib.libname")
	m.__factor_type__ = 'system'
	m.__factor_dynamics__ = 'library'
	m.name = 'libsomethingelse'
	test/library.identity(m) == 'libsomethingelse'

def test_construction_sequence(test):
	"""
	# &library.initialize of a temporary system target
	# and its subsequent &library.transform and &library.reduce.

	# ! WARNING:
		# Performs no tests aside from execution.
	"""
	tr = test.exits.enter_context(libroutes.File.temporary())
	import builtins
	import sys
	import collections

	mt = types.ModuleType("pkg.exe", "docstring")
	mt.__factor_type__ = 'system'
	mt.__factor_dynamics__ = 'executable'
	mt.__builtins__ = builtins

	sys.path.append(str(tr))
	(tr / 'pkg' / '__init__.py').init('file')
	(tr / 'pkg' / 'exe' / '__init__.py').init('file')

	pkgdir = tr / 'pkg' / 'exe'
	py = pkgdir / '__init__.py'
	src = pkgdir / 'src'
	src.init('directory')

	m = src / 'main.c'
	m.init('file')

	mt.__file__ = str(py)
	mt.__package__ = 'pkg.exe'
	test.fail("Construction execution path not tested")

if __name__ == '__main__':
	from .. import libtest; import sys
	libtest.execute(sys.modules[__name__])
