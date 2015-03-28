"""
libframe implements classes for working with a stack of compilation and linking
parameters. The :py:class:`Frame` classes, :py:class:`Compile` and :py:class:`Link`,
make up entries on the stack, :py:class:`Stack`. Items on the stack are named for
parameter tracking purposes; a given entry can be associated with some key that can be
traced back to where the parameters came from--ideally, however, as this is not enforced.

Often, compilation flags should be associated with linking flags, so the stack is
constructed to accept a pair for item, flags for compilation and linking are best accessed
with the :py:meth:`Stack.compile` and :py:meth:`Stack.link` attributes.
"""
import collections
import itertools
import contextlib

from . import libcore

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
