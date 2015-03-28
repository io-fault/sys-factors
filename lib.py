import contextlib
from .abstract import ToolError

#: Default Role used by the loader.
#: The loader will use ``'debug' if __debug__`` when nothing is specified here.
role = None

#: Target DLL Roles for compilation.
known_roles = set([
	'test',
	'debug',
	'profile',
	'coverage',
	'factor',
])

role_options = []

class Context(object):
	"""
	Context used to manage and control development build and testing processes.
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
