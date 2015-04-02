"""
Compilation bootstrapping.

In cases where libconstruct needs to perform compilation, this module can be used
independently.
"""
import sys
import os.path
import imp
import contextlib
import platform
import importlib
import itertools
import collections

from . import include # foundation includes
from . import sysconfig
from . import libcore # disabling core dumps when in Frame code

extensions = {
	'c': ('c',),
	'c++': ('c++', 'cxx', 'cpp'),
	'objective-c': ('m',),
	'ada': ('ads', 'ada'),
	'assembly': ('asm', 'a'),
	'bc': ('bc',),
}

languages = {}
for k, v in extensions.items():
	for y in v:
		languages[y] = k

class OrderedSet(object):
	"""
	Set container for filtering duplicate options.
	"""
	__slots__ = ('sequence', 'positions')

	def __init__(self, *seq):
		self.sequence = []
		self.positions = dict()
		if seq:
			self.extend(seq)

	def extend(self, seq):
		for x in seq:
			self.append(x)

	def append(self, item):
		if item not in self.positions:
			self.positions[item] = len(self.sequence)
			self.sequence.append(item)

	def __iter__(self):
		return iter(self.sequence)

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

if hasattr(imp, 'cache_from_source'):
	def cache_path(path):
		"""
		Given a module path, retrieve the basename of the bytecode file.
		"""
		return imp.cache_from_source(path)[:-len('.pyc')]
else:
	def cache_path(path):
		return path[:path.rfind('.py')]

def collect(objdir, srcdir, suffixes, suffix_delimiter = '.', join = os.path.join):
	"""
	Recursive acquire sources for compilation and build out objects.
	"""
	os.makedirs(objdir, exist_ok = True)
	prefix = len(srcdir)

	for path, dirs, files in os.walk(srcdir):
		# build out sub-directories for object cache
		for x in dirs:
			if x == '__pycache__':
				# there shouldn't be __pycache__ directories here, but ignore anyways
				continue

		for x in files:
			suffix = None

			suffix_position = x.rfind(suffix_delimiter)
			if suffix_position == -1:
				# no suffix delimiter
				continue
			else:
				# extract suffix; continue if it's not a recognized language
				suffix = x[suffix_position+1:]
				if suffix not in languages:
					continue

			srcpath = join(srcdir, path, x)
			src_suffix = srcpath[prefix+1:][:-(len(suffix)+len(suffix_delimiter))]
			objpath = join(objdir, src_suffix) + '.o'
			objpathdir = os.path.dirname(objpath)
			if not os.path.exists(objpathdir):
				os.makedirs(objpathdir, exist_ok = True)
			yield languages[suffix], srcpath, objpath

class Frame(tuple):
	"""
	A set of compilation and linking parameters for C-API module construction.
	"""
	__slots__ = ()
	def __new__(typ, **kw):
		return tuple.__new__(typ, [p(kw.get(x, ())) for x, p in zip(typ.slots, typ.process)])

	def __add__(self, add):
		return self.__class__(**dict([
			(k, getattr(self, k, ()) + getattr(add, k, ())) for k in self.slots
		]))

class Link(Frame):
	"""
	Link parameters.
	"""
	__slots__ = ()
	slots = (
		'directories',
		'libraries',
		'objects',
		'frameworks',
	)

	process = (
		tuple,
		tuple,
		tuple,
		tuple,
	)

	@property
	def directories(self):
		"""
		Directories that will be searched for library files to link against.
		"""
		return self[0]

	@property
	def libraries(self):
		"""
		Libraries that the target will be linked against.
		"""
		return self[1]

	@property
	def objects(self):
		"""
		Objects that will be statically linked into the target.
		"""
		return self[2]

	@property
	def frameworks(self):
		return self[3]

class Compile(Frame):
	"""
	Compilation parameters.
	"""
	__slots__ = ()
	slots = (
		'directories',
		'includes',
		'defines',
	)

	process = (
		tuple,
		tuple,
		lambda z: tuple([(x,y) for x, y in z]) # defines must be pairs
	)

	@property
	def directories(self):
		"""
		Directories that will be searched for header files included by C PreProcessor
		include directives.
		"""
		return self[0]

	@property
	def includes(self):
		"""
		Files to be included at the beginning of the source.
		"""
		return self[1]

	@property
	def defines(self):
		"""
		Key-Value pairs of definitions to pass to the C PreProcessor.
		"""
		return self[2]

class Independent(Frame):
	"""
	Parameters that are common to compilation and linkage.

	Currently, there are no common parameters.
	"""
	__slots__ = ()
	slots = (
		'framework_directories',
	)
	process = (
		tuple,
	)

	@property
	def framework_directories(self):
		return self[0]

class Stack(object):
	"""
	A stack of :py:class:`Compile`, :py:class:`Link`, and :py:class:`Independent`
	parameters to be used by a compiler and linker.
	"""
	__slots__ = ('_data',)

	@property
	def compile(self):
		"""
		The unique compilation parameters ordered by the position that they appeared on the
		stack.
		"""
		dirs = OrderedSet()
		incs = OrderedSet()
		defs = OrderedSet()
		fwds = OrderedSet()

		for (x, _, i) in self._data.values():
			if i:
				fwds.extend(i.framework_directories)

			if x is None:
				continue
			dirs.extend(x.directories)
			incs.extend(x.includes)
			defs.extend(x.defines)

		return {
			'directories': tuple(dirs),
			'includes': tuple(incs),
			'defines': tuple(defs),
			'framework_directories' : tuple(fwds),
		}

	@property
	def link(self):
		"""
		The unique linkage parameters ordered by the position that they appeared on the
		stack.
		"""
		dirs = OrderedSet()
		libs = OrderedSet()
		objs = OrderedSet()
		frws = OrderedSet()
		fwds = OrderedSet()

		for (_, x, i) in self._data.values():
			if i:
				fwds.extend(i.framework_directories)

			if x is None:
				continue
			dirs.extend(x.directories)
			libs.extend(x.libraries)
			objs.extend(x.objects)
			frws.extend(x.frameworks)

		return {
			'directories': tuple(dirs),
			'libraries': tuple(libs),
			'objects': tuple(objs),
			'frameworks': tuple(frws),
			'framework_directories' : tuple(fwds),
		}

	def __init__(self, Dictionary = collections.OrderedDict):
		self._data = Dictionary()

	def push(self, name,
		compile = Compile(),
		link = Link(),
		independent = Independent()
	):
		if name in self._data:
			# merge entries
			cur = self._data[name]
			self._data[name] = (
				cur[0] + compile,
				cur[1] + link,
				cur[2] + independent
			)
		else:
			# new entry
			self._data[name] = (compile, link, independent)

	def extend(self, stack):
		for id, v in stack._data.items():
			self.push(id, v[0], v[1], v[2])

	def remove(self, name):
		del self._data[name]

	def __iter__(self):
		return self._data.items()

class Context(object):
	"""
	Environment Context used to manage build options, target-wide include file, and
	environment variables to configure during the execution of build commands.

	Context objects are given to the C-API's probe module for building out the environment
	used to compile and link the extension module.
	"""
	def __init__(self, filepath = None):
		self._state = None
		self._queue = None
		self._ident = 0
		self.filepath = filepath
		self.stack = Stack()
		if filepath is not None:
			self.stack.push('context-include', compile = Compile(includes = (self.filepath,)))

	@contextlib.contextmanager
	def environment(self):
		"""
		Deploy the Probe allowing queries against the C environment to be performed.
		"""
		with tempfile.TemporaryDirectory() as d, \
		libcore.dumping(0):
			yield d

	def __enter__(self):
		self._queue = []
		self._state = open(self.filepath, 'w')
		self._stack = Stack()
		return self

	def __exit__(self, typ, val, tb):
		self.commit()
		self._state.close()
		self._state = None
		self._queue = None
		self._stack = None

	def _add_include_directory(self, param):
		self._stack.push(None, compile = Compile(directories = param))

	def _add_library_directory(self, param):
		self._stack.push(None, link = Link(directories = param))

	def _include(self, param):
		header, comment = param
		self._state.write("#include <" + header + ">\n")

	def _dynamic_link(self, param):
		self._stack.push(None, link = Link(libraries = param))

	def _define(self, param):
		for name, value in param:
			if value is None:
				self._state.write("#define " + name + "\n")
			else:
				self._state.write("#define " + name + " " + str(value) + "\n")

	def add_include_directory(self, *dirs):
		self._queue.append(('_add_include_directory', dirs))

	def add_library_directory(self, *dirs):
		self._queue.append(('_add_library_directory', dirs))

	def dynamic_link(self, *libs):
		self._queue.append(('_dynamic_link', libs))

	def define(self, **defines):
		"""
		"""
		l = list(defines.items())
		l.sort() # consistent serialization
		self._queue.append(('_define', l))

	def define_macro(self, mdef, mcontent):
		macro = mdef[0] + '(' + ', '.join(mdef[1:]) + ') \\'
		mdv = (macro, mcontent)
		self._queue.append(('_define', (mdv,)))

	def include(self, header, comment = None):
		self._queue.append(('_include', (header, comment)))

	def commit(self, framename = None):
		for meth, param in self._queue:
			getattr(self, meth)(param)
		self._queue = []
		cd = self._stack.compile
		fd = cd.pop('framework_directories')
		ld = self._stack.link
		ld.pop('framework_directories')

		# flatten the stack that was being built.
		self.stack.push(
			framename,
			compile = Compile(**cd),
			link = Link(**ld),
			independent = Independent(
				framework_directories = fd
			)
		)
		self._stack = Stack()
		self._state.flush()

	def abort(self):
		self._queue = []

class Compilation(object):
	"""
	Compile and Link C-API modules from C, C++, Objective-C, and Haskell.
	"""

	#: Call each object in this set upon a successful load of a C-API module.
	#: Normally, these callables should merely record the CLoader() instance
	#: and immediately exit.
	traceset = set()

	@classmethod
	@contextlib.contextmanager
	def tracing(cls, *callables):
		"""
		Context Manager to *signal* tracing of loaded C-API modules.
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
	dll_extension = '.pyd'

	@property
	def directory(self, dirname = os.path.dirname):
		return dirname(self.source)

	@property
	def defines(self):
		"""
		Loader-level defines given to the compiler.
		"""
		role = 'bootstrap'
		# And the individual bits.
		roptions = dict()
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

		if self.package is not None:
			package = [
				('MODULE_PACKAGE', '"' + self.package + '"'),
			]
		else:
			package = []

		return package + [
			('MODULE_BASENAME', self.name),
			('MODULE_QNAME', '"' + self.fullname + '"'),
			('INIT_FUNCTION', 'PyInit_' + self.name),
			# Near transparent 2.x support.
			('INIT_FUNCTION_COMPAT', 'init' + self.name),
		] + role_options

	def __init__(self, pkg, name, target, subjects, sources, role = None, options = ()):
		self.tools = sysconfig.Toolset(role)
		self.role = role
		self.sources = sources
		self.package = pkg
		self.name = name
		self.target = target
		self.subjects = subjects

		if pkg is None:
			self.fullname = name
		else:
			self.fullname = '.'.join((pkg,name))

	def build(self, context = None):
		context = Context()
		copts = context.stack.compile

		defines = self.defines
		defines.extend(copts['defines'])

		cofs = []
		for lang, src, cof in self.subjects:
			incs = (include.xpython, include.cpython,) + copts['includes']
			compile = self.tools.compile(
				cof, lang, src,
				defines = defines,
				includes = incs,
				directories = copts['directories'],
				framework_directories = copts['framework_directories'],
			)
			self.tools.stage('compile', cof, cof + '.log', compile)
			cofs.append(cof)

		lopts = context.stack.link
		cofs.extend(lopts['objects'])
		link = self.tools.link(
			self.target, *cofs,
			directories = lopts['directories'],
			libraries = lopts['libraries'],
			frameworks = lopts['frameworks'],
			framework_directories = lopts['framework_directories']
		)
		self.tools.stage('link', self.target, self.target + '.log', link)

	def load(self, load_dynamic = imp.load_dynamic, exists = os.path.exists, getmtime = os.path.getmtime):
		fsconditions = (not exists(self.target) or getmtime(self.target) < getmtime(self.sources))
		if fsconditions:
			exc = self.build()
			if exc is not None:
				raise ImportError(self.fullname) from exc

		try:
			mod = load_dynamic(self.name, self.target)
		except Exception:
			raise ImportError(self.name)

		for x in self.traceset:
			x(self)
		return mod

def config(role, module_dict, source_directory):
	"""
	Given a package module's dictionary, build the necessary details for locating
	source files and storing object files.
	"""
	parent = module_dict['__package__']
	dir = os.path.dirname(os.path.abspath(module_dict['__file__']))
	srcdir = os.path.join(dir, source_directory)
	pkg, name = module_dict['__name__'].rsplit('.', 1)

	cache_name = '{role}:python-{version}{abiflags}.{platform}'.format(
		role = role,
		abiflags = sys.__dict__.get('abiflags', ''),
		version = ''.join(map(str, sys.version_info[:2])),
		platform = Compilation.platform,
	)
	# For instance, project/pkg/__pycache__/debug:abi.linux/subdir/foo.c
	objdir = os.path.join(dir, '__pycache__', cache_name)

	# list of (language, source_filepath, object_filepath) tuples.
	srcobj = list(collect(objdir, srcdir, languages))

	return {
		'src': srcdir,
		'obj': objdir,
		'package': pkg,
		'name': name,
		'subject': srcobj,
		'target': os.path.join(objdir, 'module.pyd')
	}

def select_role():
	# use override if available; otherwise, use global role in this module
	if role is None:
		default_role = sys.modules[__name__].role
		if default_role is None:
			role = ('debug' if __debug__ else 'factor')
		else:
			role = default_role
	ctx['__role__'] = role

def construct(foundation = None, source_directory = 'src'):
	"""
	Execute within a package module containing a 'src' directory to build the C-API
	module using bootstrap's @Compilation.
	"""
	ctx = outerlocals()

	cfg = config('bootstrap', ctx, source_directory = source_directory)
	cl = Compilation(cfg['package'], cfg['name'], cfg['target'], cfg['subject'], cfg['src'], role = 'bootstrap')

	# rewrite the package module contents with that of the extension module
	m = cl.load()
	for k, v in m.__dict__.items():
		if k.startswith('__'):
			continue
		ctx[k] = v
	ctx['__shared_object__'] = m
	ctx['__bootstrap__'] = cl
