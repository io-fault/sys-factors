"""
Project development interfaces for software engineers.
"""
import functools
import typing

from ..routes import library as libroutes
from ..xml import lxml
from ..xml import library as libxml

namespaces = {
	'xlink': 'http://www.w3.org/1999/xlink',
	'inspect': 'https://fault.io/xml/inspect#set',
}

def python_context(implementation, version_info, abiflags, platform):
	"""
	Construct the triplet representing the Python context for the platform.
	Used to define the construction context for Python extension modules.
	"""
	pyversion = ''.join(map(str, version_info[:2]))
	return '-'.join((implementation, pyversion + abiflags, platform))

class Factor(tuple):
	"""
	The abstract factor that makes up part of a product.
	Essentially, the route and factor type with respect to construction,
	but also higher level interfaces for supporting construction.
	"""
	__slots__ = ()

	@classmethod
	def from_module(Class, module):
		mt = getattr(module, '__factor_type__', 'python-module')
		return Class((mt, libroutes.Import.from_fullname(module.__name__)))

	@classmethod
	def from_fullname(Class, path, Import=libroutes.Import.from_fullname):
		i = Import(path)
		module = i.module()
		mt = getattr(module, '__factor_type__', 'python-module')
		return Class((mt, i))

	@property
	def type(self):
		"The module's `__factor_type__` attribute."
		return self[0]

	@property
	def route(self):
		"The route to the module."
		return self[1]

	@property
	def source_route(self):
		return (self[1].file().container / 'src')

	@staticmethod
	def _canonical_path(route):
		x = route
		while x.points:
			m = x.module()
			mt = getattr(m, '__factor_type__', None)
			if mt == 'context':
				yield getattr(m, '__canonical__', None) or x.identifier
			else:
				yield x.identifier
			x = x.container

	@property
	@functools.lru_cache(32)
	def name(self, list=list, reversed=reversed):
		"""
		The canonical factor name.
		"""
		l = list(self._canonical_path(self[1]))
		return '.'.join(reversed(l))

	def sources(self) -> typing.Sequence[libroutes.File]:
		"""
		The full set of source files of the factor.
		"""
		types = {'system.executable', 'system.extension', 'system.library', 'system.object'}

		if self.type in types:
			fr = self.source_route
			return fr.tree()[1]
		else:
			s = self.route.spec()
			if s is not None and s.has_location:
				return [libroutes.File.from_absolute(s.origin)]
			else:
				m = self.route.module()
				if m.__file__:
					return (libroutes.File.from_absolute(m.__file__),)
				else:
					return ()

class Project(object):
	"""
	A unit containing targets to be constructed or processed.
	Provides access to project information and common project operations.

	The project's outermost package module must identify itself as the floor
	in order for &Project to function properly.

	! WARNING:
		Do not use. Currently, a conceptual note.
	"""

	def __init__(self, route):
		self.route = route
		self.directory = self.route.file().container

	@classmethod
	def from_module(Class, module, Import = libroutes.Import):
		"Return the &Project instance for the given module path."
		r = Import.from_module(module)
		return Class(r.floor())

	@property
	def information(self):
		"The package's project module. Provides branch information and identity."
		pim = self.route / 'project'
		return pim.module()

	@property
	def qid(self):
		"The package's qualified identity. Uniquely identifies the project and variant."
		pi = self.information
		return '#'.join((pi.identity, pi.fork))

	def initialize(self, role='factor'):
		"""
		Initialize the project so that it may be usable and ready for installation.

		This method will perform the necessary compilation tasks for a production installation.
		"""
		pass

	def validate(self):
		"""
		Validate the functionality of the project.

		This method initializes the project for a "test" role and performs all available tests.
		It does *not* perform coverage analysis.
		"""
		self.initialize('test')
		self.test('test')
		self.test()

	def test(self, role='factor'):
		"""
		Perform the project's tests for the given role.
		"""

	def release(self):
		"""
		Modify the package to become a release.
		"""

def extract_inspect(xml, href='{%s}href' %(namespaces['xlink'],)):
	"""
	Load the factor of an inspect role run.

	[Effects]

	/return
		A pair, the former being the command parameters and the latter
		being the set of sources.
	"""
	global namespaces

	e = xml.getroot()

	# Stored parameters of the link. (library.set)
	params = e.find("./inspect:parameters", namespaces)
	if params is not None:
		data, = params
		s = libxml.Data.structure(data)
	else:
		s = None

	# Source file.
	sources = e.findall("./inspect:source", namespaces)
	sources = [libroutes.File.from_absolute(x.attrib[href].replace('file://', '', 1)) for x in sources]

	return s, sources

class DevelopmentException(Exception):
	"""
	Base class for exceptions that are related to the development of software.

	Development exceptions are used to classify a set of exceptions that are
	used to define errors that are ultimately caused by the development process
	itself.
	"""

	def __init__(self, reference, message, **paramters):
		self.reference = reference
		self.message = message
		self.parameters = paramters

	def __str__(self):
		return self.message

class PendingImplementationError(DevelopmentException):
	"""
	Raised in cases where the software does not yet exist.
	"""
