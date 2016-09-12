"""
Project management interfaces for dynamically defining a set of targets.
"""
import functools
import typing

from ..routes import library as libroutes
from ..system import libfactor

class Factor(object):
	from ..computation import libhash
	_hash_r = libhash.reference('fnv1a_64')
	del libhash

class Unit(Factor):
	"""
	The abstract factor that makes up part of a product.
	Essentially, the route and factor type with respect to construction,
	but also higher level interfaces for supporting construction.

	[Properties]

	/type
		The factor type. For composites sources, this must be set
		to `'fraction'`.
	/context
		The &.libroutes.Import pointing to the root context package.
		&None if there is no context factor containing this &Unit.
	/project
		The &.libroutes.Import pointing to the project package. &None
		if there is no project.
	/route
		The &.libroutes.Import selecting the subject factor.
		If the selected subject factor is the &project, then these
		are equal. Likewise with &context.
	"""
	type = None
	context = None
	project = None
	route = None

	def hash(self) -> str:
		"""
		Calculate the hash data for the Unit.
		"""
		h = self._hash_r()
		h.update(self.source.load())
		return h.hexdigest()

	@property
	def is_package(self):
		"""
		Whether the factor is a package module.
		"""
		return self.route.identifier.startswith('__init__.')

	@property
	def is_composite(self):
		"""
		Whether the factor is a composite.
		"""
		return libfactor.composite(self.route)

	@property
	def is_terminal(self):
		"""
		Whether there are any subfactors of any kind.
		"""
		return self.is_package()

	@classmethod
	def from_filesystem(Class, path):
		"""
		Construct the &Factor from a path on the file system. All information
		will be inferred using directory protocols and by scraping the module's source.
		"""
		pass

	@property
	def source_route(self):
		"""
		Route to the composite's source directory.
		"""
		return (self.module_file.container / 'src')

	@staticmethod
	def _canonical_path(route):
		x = route
		while x.points:
			m = x.module()
			mt = getattr(m, '__factor_type__', None)
			if mt == 'context':
				yield getattr(m, '__factor_cname__', None) or x.identifier
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
		pass

	def __str__(self):
		return 'file://%s#%s' %(self.context, str(self.route))
		#return r + '' if self.fraction is None else ('/' + '/'.join(self.fraction.points))

	@classmethod
	def from_module(Class, module):
		"""
		Construct a &Factor instance from an imported module.
		"""
		mt = getattr(module, '__factor_type__', 'python-module')
		ir = libroutes.Import.from_fullname(module.__name__)

		# Root package's ancestor directory should be the filesystem context directory.
		rpkg = ir.root
		ctx = rpkg.file() ** 2

		mf = ir.file()
		is_composite = libfactor.composite(ir)
		project = ir.floor()
		fp = ir.absolute
		ir = libroutes.Import(project, fp[len(project.absolute):])

		return Class(ctx, mt, project, ir)

	@property
	def source(self):
		"""
		Route to the source file of the factor.
		"""
		return self.route.file()

	@staticmethod
	def _scrape(route:libroutes.File, *keys):
		"""
		Scrape the file for the given keys. Presumes single line settings.
		"""
		for l in route.load(mode='r').split('\n'):
			var, *tail = l.split('=', 1)
			if tail:
				k = var.strip()
				if k in keys:
					yield (k, tail[0].strip(" \t'" + '"'))

	@classmethod
	def _get_project_identity(Class, route:libroutes.File, key='identity'):
		"""
		Retrieve the project identity from the (python:module)`project`
		module file.
		"""
		return dict(Class._scrape(route, key)).get(key)

	@classmethod
	def _get_factor_type(Class, route:libroutes.File, key='__factor_type__'):
		"""
		Retrieve the project identity from the (python:module)`project`
		module file.
		"""
		return dict(Class._scrape(route, key)).get(key)

	@property
	def uri(self):
		"""
		Resource indicator for universal access to the factor.
		"""
		proj = (self.project / 'project')
		proj_path = self.context.extend(proj.absolute).suffix('.py')
		root_url = self._get_project_identity(proj_path)

		#mod = proj.route().identity + '.' + '.'.join(self.route.points)
		url = root_url + '.' + '.'.join(self.route.points)
		return url
		#return mod + '/' + '/'.join(self.fraction.points)

	def __init__(self, *args):
		self.context, self.type, self.project, self.route = args

#f = Unit.from_module(libroutes)
#print(str(f))
#print(f.source)
#print(f.iri)
#print(f.hash())

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
