"""
Loader implementation for automatic compilation and linking of C-API extensions upon import.
"""
import sys
import os.path
import imp
import importlib.abc
import importlib.machinery
import contextlib
import platform

from . import include # loader includes
from . import sysconfig

role = None
role_options = []

if hasattr(imp, 'cache_from_source'):
	def cache_path(path):
		"""
		Given a module path, retrieve the basename of the bytecode file.
		"""
		return imp.cache_from_source(path)[:-len('.pyc')]
else:
	def cache_path(path):
		return path[:path.rfind('.py.')]

# Suffixes used to identify modules.
module_suffixes = set(importlib.machinery.all_suffixes() + [
	'.py.c', '.py.cxx', '.py.m', '.py.hs'
])

class CLoader(importlib.abc.InspectLoader, importlib.abc.Finder):
	"""
	Compile and Link C-API modules from C, C++, Objective-C, and Haskell.
	"""
	def get_code(self, module):
		pass

	def get_data(self, module):
		pass

	def get_filename(self, name):
		return self.source

	def get_source(self, name):
		with open(self.source) as f:
			return f.read()

	def is_package(self, *args, **kw):
		'CLoader does not handle packages. Always returns :py:obj:`False`'
		return False

	#: Call each object in this set upon a successful load of a C-API module.
	#: Normally, these callables should merely record the CLoader() instance
	#: and immediately exit.
	traceset = set()

	@classmethod
	@contextlib.contextmanager
	def tracing(cls, *callables):
		"""
		Context Manager to enable tracing of loaded C-API modules.
		"""
		stored = set(cls.traceset)
		try:
			cls.traceset.update(tuple(callables))
			yield None
		finally:
			cls.traceset.clear()
			cls.traceset.update(stored)

	platform = platform.system().lower() + '.' + platform.machine().lower()
	target = platform

	stages = (
		'prepare',
		'compile',
		'link',
	)

	types = [
		('c', '.py.c'),
		('objc', '.py.m'),
		('c++', '.py.cxx'),
	]

	dll_extension = '.pyd'

	@property
	def directory(self, dirname = os.path.dirname):
		return dirname(self.source)

	@property
	def probename(self):
		"""
		Qualified Path to the module managing the necessary probes for compilation and
		linkage.

		Extension modules with Probes must be nested inside a package module.
		"""
		if self.package is not None:
			return '.'.join((self.package, 'xprobe', self.name))
		return None

	@property
	def probe_module(self):
		"""
		The module used to probe the system for compilation information.
		"""
		if self.package is None:
			return None

		try:
			mod = importlib.import_module(self.probename)
			del sys.modules[mod.__name__]
			return mod
		except ImportError:
			return None

	@property
	def defines(self):
		"""
		Loader-level defines given to the compiler.
		"""
		if self.package is not None:
			package = [
				('MODULE_PACKAGE', '"' + self.package + '"'),
			]
		else:
			package = []

		role = self.tools.role
		# And the individual bits.
		roptions = dict(self.role_options)
		roptions.setdefault(role, ())

		# Define the role's value.
		rflags = sum([1 << y for y in range(len(roptions[role]))])

		role_options = [
			('xxx' + role.upper() + 'xxx', str(1 << 32 | rflags)),
			('xxx' + role.upper() + 'x', str((1 << 33) - 1)), # any
			('xxx' + role.upper() + 'x' + 'ROLE', str(1 << 32)),
		]

		for role in roptions:
			rid = role.upper()
			role_options.extend([
				('xxx' + rid + 'x' + x, str(1 << y))
				for x, y in zip(roptions[role], range(30))
			])

		return package + [
			('MODULE_BASENAME', self.name),
			('MODULE_QNAME', '"' + self.fullname + '"'),
			('INIT_FUNCTION', 'PyInit_' + self.name),
			# Near transparent 2.x support.
			('INIT_FUNCTION_COMPAT', 'init' + self.name),
		] + role_options

	def logfile(self, stage):
		return '.'.join((self.cprefix, stage, 'log'))

	def crofile(self):
		'C Role Options file'
		return '.'.join((self.cprefix, 'cro'))

	def croptions(self):
		'String Represention of configured Croptions'
		return '\n'.join([
			x + '=' + '|'.join(y) for (x,y) in self.role_options
		])

	def cropdate(self):
		'Whether or not the configured croptions match the current build.'
		with open(self.crofile(), 'r') as crofile:
			return self.croptions() == crofile.read()

	def execute(self, stage, command):
		logfile = self.logfile(stage)
		if os.path.exists(logfile):
			os.unlink(logfile)
		return self.tools.dispatch(logfile, stage, command).wait()

	def __init__(self, pkg, name, source, type = 'c', role = None, options = ()):
		role = role or ('debug' if __debug__ else 'factor')
		self.tools = sysconfig.Toolset(role)
		self.role = role

		self.role_options = options
		if self.role_options:
			# for consistent .cro file representation
			self.role_options.sort()
			for v in self.role_options:
				v[1].sort()

		self.type = type
		self.package = pkg
		self.name = name

		if pkg is None:
			self.fullname = name
		else:
			self.fullname = '.'.join((pkg,name))

		self.path = self.source = source
		self.cprefix = cache_path(source) + sys.__dict__.get('abiflags', '')

		self.cprefix += '.' + self.platform
		self.cprefix += ('.' + self.tools.role)

		self.dll = self.cprefix + self.dll_extension

	@classmethod
	def find_module(typ, fullname,
		paths = None,
		realpath = os.path.realpath,
		join = os.path.join,
		exists = os.path.exists,
	):
		names = fullname.split('.')
		modname = names[-1]

		if paths is None:
			paths = sys.path
			suffix = join(*names)
		else:
			suffix = modname

		# XXX: per-module and package-prefix overrides for roles and options.
		lrole = role
		lrole_options = list(role_options)

		for f in paths:
			path = join(realpath(f), suffix)
			for type, ext in typ.types:
				source = path + ext
				if exists(source):
					prefix = '.'.join(names[:-1])
					return typ(
						prefix, modname, source,
						type = type, role = lrole,
						options = lrole_options
					)

	def build(self, context = None):
		dir = os.path.dirname(self.cprefix)
		if not os.path.exists(dir):
			os.mkdir(dir)

		# get probe module for initializing the context
		probes = self.probe_module
		if probes is not None:
			if context is None:
				from . import libframe
				# build out a context for the probes
				context = libframe.Context(self.cprefix + '.h')

			probes.initialize(context)
			with context:
				# XXX: hack to force header file write.
				pass
		else:
			from . import libframe
			# empty context
			context = libframe.Context()

		copts = context.stack.compile

		defines = self.defines
		defines.extend(copts['defines'])

		with open(self.crofile(), 'w') as crofile:
			crofile.write(self.croptions())

		incs = (include.xpython, include.cpython,) + ((include.objcpython,) if self.type == 'objc' else ()) + copts['includes']

		cof = self.cprefix + self.tools.compile_output_extension
		compile = self.tools.compile(
			cof, self.type, self.source,
			defines = defines,
			includes = incs,
			directories = copts['directories'],
			framework_directories = copts['framework_directories'],
		)

		lopts = context.stack.link
		link = self.tools.link(
			self.dll, self.type, cof, *lopts['objects'],
			directories = lopts['directories'],
			libraries = lopts['libraries'],
			frameworks = lopts['frameworks'],
			framework_directories = lopts['framework_directories']
		)

		self.tools.stage('compile', cof, self.logfile('compile'), compile)
		self.tools.stage('link', self.dll, self.logfile('link'), link)

	def load(self, load_dynamic = imp.load_dynamic):
		try:
			mod = load_dynamic(self.name, self.dll)
			mod.__cached__ = self.dll
			mod.__loader__ = self
			mod.__file__ = self.source
		except Exception:
			raise ImportError(self.name)

		return mod

	def load_module(self, fullname,
		exists = os.path.exists,
		getmtime = os.path.getmtime,
	):
		fsconditions = (not exists(self.dll) or getmtime(self.dll) < getmtime(self.source))
		if fsconditions or not self.cropdate():
			exc = self.build()
			if exc is not None:
				raise ImportError(self.fullname) from exc
		mod = sys.modules[self.fullname] = self.load()
		for x in self.traceset:
			x(self)
		return mod

	def module_repr(self, module):
		return object.__repr__(module)

def install(role_override = None):
	"""
	Install the meta path hook for importing [foreign] C-API modules.
	"""
	global role
	global role_options
	if 'development-role' in sys._xoptions:
		role = sys._xoptions['development-role']

	if role is not None:
		role = role

	if 'croptions' in sys._xoptions:
		opts = sys._xoptions['croptions']
		role_options.extend([
			(k, list(v.split('|'))) for (k, v) in
			[x.split(':') for x in opts.split(',') if ':' in x]
		])

	if CLoader not in sys.meta_path:
		sys.meta_path.append(CLoader)

	importlib.machinery.all_suffixes = lambda: list(module_suffixes)

def remove():
	'Remove the meta path hook.'
	sys.meta_path.remove(CLoader)
