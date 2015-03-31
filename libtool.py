"""
Toolsets and utilities for compiling executables and shared objects using system commands.
"""
import sys
import os
import os.path
import shutil
import functools
import subprocess
import importlib

from . import abstract
from . import libprobe
from . import libframe

from ..routes import library as routeslib

assemblers = set((
	shutil.which('nasm'),
	shutil.which('yasm'),
))

class Toolchain(abstract.Linked):
	"""
	Toolchain for compiling and linking executables, shared libraries, and dynamically
	loaded libraries.
	"""
	role = None

	if sys.platform == 'win32':
		role_compile_flags = {
			'factor': ('/Ox',),
			'debug': ('/Od', '/DEBUG'),
			'test': ('/Od', '/DEBUG'),
		}

		role_link_flags = {
			'test': ('/DEBUG',),
			'debug': ('/DEBUG',),
			'factor': (),
		}
	else:
		role_compile_flags = {
			'factor': ('-O3', '-g'),
			'debug': ('-O0', '-g'),
			'test': ('--coverage', '-O0', '-g'),
		}

		role_link_flags = {
			'test': ('--coverage', '-ftest-coverage', '-fprofile-arcs'),
			'factor': (),
		}

	@classmethod
	def cdarwin(typ, t, language):
		return (typ.default_compiler(), '-x', language)

	@classmethod
	def cunix(typ, t, language):
		return (typ.default_compiler(), '-x', language)

	@classmethod
	def cwindows(typ, t, language):
		return ('cl.exe',)

	@classmethod
	def ldll(typ, t, name, version = None, loader = None):
		if t == 'bin':
			tfalgs = ()
			suffix = 'exe'
			placement = 'precede'
		elif t == 'lib':
			tflags = ('/dll',)
			suffix = 'dll'
			placement = 'precede'
		elif t == 'libexec':
			tflags = ('/dll',)
			suffix = 'dyn'
			placement = 'precede'

		return placement, suffix, (typ.default_linker(),)

	@classmethod
	def ldylib(typ, t, name, version = None, loader = None):
		"""
		Link .dylib libraries. (macosx/darwin)
		"""
		if t == 'bin':
			tflags = ('-execute', '-lcrt1.o')
			suffix = 'exe'
			placement = 'proceed'
		elif t == 'lib':
			tflags = ('-dylib', '-dead_strip_dylibs',)
			suffix = 'dylib'
			placement = 'precede'
		elif t == 'libexec':
			suffix = 'dylib'
			placement = 'precede'

			if loader is None:
				# Assume unknown or unimportant.
				# Many platforms don't require knowledge of the loader.
				tflags = ('-bundle', '-undefined', 'dynamic_lookup',)
			else:
				tflags = ('-bundle', '-bundle_loader', loader,)

		return placement, suffix, (typ.default_linker(), '-t') + tflags + ('-framework', 'Foundation')

	@classmethod
	def lelf(typ, t, name, version = None, loader = None):
		"""
		Link ELF libraries. (shared objects on most unix systems)
		"""
		if t == 'bin':
			# default is executable
			tflags = ()
			suffix = 'exe'
			placement = 'proceed'
		elif t  == 'lib' and version is not None:
			# shared, soname'd with version ("libname.so.M.N")
			vstr = '.'.join(map(str, version[:2]))
			tflags = ('-shared', '-soname',  '.so.'.join((name, vstr)))
			suffix = 'so'
			placement = 'proceed'
		else:
			tflags = ('-shared',)
			suffix = 'so'
			placement = 'proceed'

		return placement, suffix, (typ.default_linker(),) + tflags + ('-framework', 'Foundation')

	if sys.platform == 'darwin':
		compiler = cdarwin
		_linker = ldylib
	elif sys.platform == 'win32':
		#compiler = cwin
		_linker = ldll
	else:
		compiler = cunix
		_linker = lelf

	def linker(self, t, name, version = None, **kw):
		kw['version'] = version
		version_place, suffix, fragment = self._linker(t, name, **kw)

		if version is not None:
			vstr = tuple(map(str, version))
			if version_place == 'proceed':
				pass
			elif version_place == 'precede':
				pass
		else:
			pass

		return name + '.' + suffix, (), fragment

	@staticmethod
	def default_compiler(default = 'clang'):
		return shutil.which(os.environ.get('CC', default))

	@staticmethod
	def default_linker(default = 'ld'):
		return shutil.which(os.environ.get('LINKER', default))

	@staticmethod
	def default_strip(default = 'strip'):
		return shutil.which(os.environ.get('STRIP', default))

	@staticmethod
	def default_objcopy(default = 'objcopy'):
		return shutil.which(os.environ.get('OBJCOPY', default))

	def __init__(self,
		type = 'executable',
		role = 'factor',
		compiler = None,
		linker = None,
	):
		self.type = type
		self.role = role

	def compile(self,
		language, target, sources,
		defines = (),
		includes = (),
		directories = (),
		dependency = None,
	):
		"""
		:param defines: A sequence of key-value pairs that make up parameter defines.
		:type defines: (:py:class:`str`, :py:class:`str`)
		:param includes: A sequence of files that will be directly included in the source.  (-include)
		:type includes: :py:class:`str`
		:param directories: A sequence of include and framework directories. (-I and -F on applicable platforms)
		:type directories: :py:class:`str`
		"""
		flags = ('-v', '-fPIC',)

		cc = self.compiler(self.type, language)

		ldirectories = ()
		ldirectories += tuple(['-I' + x for x in directories])

		ldefines = tuple([
			'-D' + (k if v is None else k + '=' + v)
			for k, v in defines
		])

		lincludes = []
		for x in includes:
			lincludes.extend(('-include', x,))
		lincludes = tuple(lincludes)

		if dependency is not None:
			dflags = ('-MD', '-MT', 'none', '-MF', dependency)
		else:
			dflags = ()

		return cc + flags + dflags + self.role_compile_flags.get(self.role, ()) \
			+ ldirectories + ldefines + lincludes + ('-o', target, '-c') + sources

	def link(self,
		targetdir, name,
		version, objects,
		loader = None,
		libraries = (),
		directories = (),
		frameworks = (),
		linker = None
	):
		"""
		:param directories: A sequence of library and framework directories. (-L, -F on some systems)
		:type directories: (:py:class:`str`)
		:param libraries: A sequence of libraries to dynamically link against the target. (-l)
		:type libraries: :py:class:`str`
		:param frameworks: A sequence of frameworks to use for linkage; library sets (-framework)
		:type frameworks: (:py:class:`str`)
		"""
		basename, canons, link = self.linker(self.type, name, version = version)
		target = os.path.join(targetdir, basename)

		ldirectories = tuple(['-L' + x for x in directories])
		llibraries = tuple(['-l' + x for x in libraries])

		role_flags = self.role_link_flags.get(self.role, ())

		return (
			target, canons,
			link + role_flags + ldirectories + \
			llibraries + ('-v', '-o', target) + tuple(objects)
		)

	if sys.platform == 'darwin':
		def isolate(self, target):
			dtarget = target + '.dSYM'
			return dtarget, [
				('dsymutil', target, '-o', dtarget)
			]
	else:
		def isolate(self, target):
			"""
			Isolate debugging information from the target.
			"""
			oc = self.default_objcopy()
			strip = self.default_strip()

			d = os.path.dirname(target)
			b = os.path.basename(target)
			debug = b + '.debug'

			return [
				(oc, '--only-keep-debug', target, os.path.join(d, debug)),
				(strip, '--strip-debug', '--strip-unneeded', target),
				(oc, '--add-gnu-debuglink', target, debug),
			]

	def stage(self,
		id, target, reference,
		popen = subprocess.Popen,
		exists = os.path.exists,
	):
		"""
		Execute the stage recording progress information to the given logfile path.
		"""
		# stdout/stderr sent to the logfile.
		logfile = target + '.' + id + '.log'

		with open(logfile, 'w') as log:
			pass

		for x in reference:
			with open(logfile, 'a') as log:
				log.write('\n--------\n')
				log.write(' '.join(x))
				log.write('\n--------\n\n')
				log.flush()

				r = popen(x, stdout = log, stderr = subprocess.STDOUT, stdin = None)
				if r.wait() != 0:
					raise abstract.ToolError(id, target, log)

		if not exists(target):
			with open(logfile, 'rb') as f:
				log = f.read().decode('utf-8', errors='replace').strip()
			raise abstract.ToolError(id, target, log)

def outerlocals(depth = 0):
	"""
	Get the locals dictionary of the calling context.

	If the depth isn't specified, the locals of the caller's caller.
	"""
	if depth < 0:
		raise TypeError("depth must be greater than or equal to zero")

	f = sys._getframe().f_back.f_back
	while depth:
		depth -= 1
		f = f.f_back
	return f.f_locals

def prepare(srcdir, join = os.path.join, languages = {
	'c': 'c',
	'cxx': 'c++',
	'm': 'objc',
	'ads': 'ada',
	'ada': 'ada',
	'asm': 'asm',
	'bc': 'bc',
}):
	"""
	Recursive acquire sources for compilation and build out objects.
	"""
	cache = os.path.join(srcdir, '__pycache__')
	os.makedirs(cache, exist_ok = True)
	prefix = len(srcdir)

	for path, dirs, files in os.walk(srcdir):
		if os.path.basename(path) == '__pycache__':
			continue

		# build out sub-directories for object cache
		for x in dirs:
			if x == '__pycache__':
				continue

			fragment = os.path.join(path, x)[prefix+1:]
			os.makedirs(os.path.join(cache, fragment), exist_ok = True)

		for x in files:
			suffix_position = x.rfind('.')
			if suffix_position != -1:
				suffix = x[suffix_position+1:]
				if suffix in languages:
					yield languages[suffix], join(path, x)

# retrieve cache or initialize context
def initialize_context(language, func):
	ctx = libframe.Context()
	func(libprobe, ctx)
	return ctx

def Initialize(module):
	"""
	Initialize the target of the given package module.
	"""
	join = os.path.join
	basename = os.path.basename
	dirname = os.path.dirname

	ol = module.__dict__

	# collection of sources
	srcdir = dirname(ol['__file__'])
	# the target module
	pkg = ol['__package__']

	pkgparts = pkg.split('.')

	# pkg's package
	container = '.'.join(pkgparts[:-2])

	ol['kind'] = target = pkgparts[-2]

	# dependencies
	deps = [
		Initialize(importlib.import_module(x, package = container))
		for x in ol.get('frameworks', ())
	]

	ol['modules'] = deps

	contexts = dict([
		(typ, initialize_context(typ, cinit))
		for typ, cinit in ol.get('_initializors', ())
	])

	# import the descendant modules and initialize their targets if any
	# (C fragment generation)
	route = routeslib.Import.from_fullname(pkg)
	tpkgs, tmods = route.tree()
	for x in tpkgs + tmods:
		if x.fullname.endswith('__main__'):
			continue

		m = x.module()
		if hasattr(m, 'initialize'):
			suffix, dependencies = m.initialize()

	# name of the target
	name = basename(srcdir)
	# where the target is located
	outdir = dirname(srcdir)

	# targets should be two levels deep: project/class/target/*.src
	project = dirname(outdir)

	# The project's library and dynamic library directories.
	libdir = join(project, 'lib') # ../lib
	# dynamically loaded modules
	libexec = join(project, 'libexec')

	# The include directory of the entire
	libincdir = join(libdir, 'include')
	# local inc directory
	incdir = join(srcdir, 'include')

	ol['includes'] = incdir

	incs = (incdir,)
	for m in deps:
		incs += (m.includes,)

	sources = list(prepare(srcdir))

	ol['source_directory'] = srcdir
	ol['sources'] = [f for l, f in sources]
	v = ol['version_info'][:2]

	prefix = len(srcdir)
	objdir = join(srcdir, '__pycache__')
	triples = [(l, f, f[prefix + 1:]) for l, f in sources]
	objects = []

	chain = Toolchain(type = target)
	for l, s, o in triples:
		obj = join(objdir, o)
		objects.append(obj)
		cs = chain.compile(l, obj, (s,),
			dependency = obj + '.dep',
			directories = (libincdir, incdir))
		chain.stage('compile', obj, (cs,))

	libs = getattr(module, 'libraries', ())
	ltarget, lcanon, link = chain.link(
		outdir, name, v, objects,
		libraries = libs
	)
	chain.stage('link', ltarget, (link,))

	dtarget, commands = chain.isolate(ltarget)
	chain.stage('isolate', dtarget, commands)

	module.product = ltarget
	module.canonical = lcanon

	return module

def execution():
	ol = outerlocals(0)
	pkg = ol['__package__']
	mod = importlib.import_module(pkg)
	Initialize(mod)
	if mod.kind == 'bin':
		p = subprocess.Popen((mod.product,) + tuple(sys.argv[1:]))
		sys.exit(p.wait())
	else:
		# remote library information
		print('executed ' + mod.kind)

def Language(typ):
	ol = outerlocals(0)
	ol.setdefault('_initializors', [])
	inits = ol['_initializors']
	def outer(func):
		inits.append((typ, func))
		return func
	return outer
