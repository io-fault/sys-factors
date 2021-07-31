"""
# Core classes and data structures for building projects with Construction Contexts.
"""
import sys
import typing
import functools
import itertools
import operator

from fault.context import tools
from fault.system import files
from fault.project import system as lsf

class SystemFactor(object):
	"""
	# Target representing a system factor.
	"""

	fields = {
		'source-paths': {'http://if.fault.io/factors/lambda.sources'},
		'image': {
			'http://if.fault.io/factors/system.library',
			'http://if.fault.io/factors/system.directory',
		},
		'parameters': {'http://if.fault.io/factors/lambda.control'},
	}

	@property
	def absolute(self):
		return ()

	@property
	def project(self):
		return None

	@property
	def route(self):
		return None

	@property
	def symbols(self):
		# System factors are always final and dependencies are irrelevant.
		return {}

	def __init__(self, type, data):
		self.type = type
		self.data = data

	def sources(self):
		return self.data

	def image(self, variants):
		return self.data

	def get(self, field):
		typset = self.fields[field]
		if str(self.type) not in typset:
			raise ValueError("field is not available under factor type")

		return self.data

class Target(object):
	"""
	# The representation of a Project Factor as a compilation target.
	"""

	# flatten for &select and vector compositions.
	fields = {
		'factor-index': ('route', 'container'),
		'factor-type': ('type',),

		'factor-relative-path': ('route',),
		'factor-path': ('absolute',),
		'project-path': ('project', 'factor'),
		'context-path': ('project', 'factor', 'container'),

		'factor-name': ('route', 'identifier'),
		'project-name': ('project', 'factor', 'identifier'),
		'context-name': ('project', 'factor', 'container', 'identifier'),

		'factor-id': ('_factor_id',),
		'project-id': ('project', 'identifier'),
		'context-id': ('_context_id',),

		'corpus': ('_corpus_id',),
		'source-paths': ('_source_paths',),
		'sources': ('_source_list',),
	}

	@property
	def _factor_id(self):
		return '/'.join((self.project.identifier, str(self.route)))

	@property
	def _context_id(self):
		for ctx in self.context.itercontexts(self.project):
			return ctx.identifier

	@property
	def _corpus_id(self):
		path = self.project.identifier
		final = path.rfind('/')
		return path[:final+1]

	@property
	def _source_list(self):
		return self.sources()

	@property
	def _source_paths(self):
		for (fp, ft), fs in self.project.select(self.route.container):
			if fp == self.route:
				for x in fs[1]:
					return x[1].context

	def get(self, field):
		# Get the (local) field requested by &select.
		obj = self
		for attr in self.fields[field]:
			obj = getattr(obj, attr) # invalid field path?
		return obj

	def __repr__(self):
		return "<%s:%s>" %(self.type, self.route)

	def __r_repr__(self):
		return "{0.__class__.__name__}({1})".format(
			self,
			', '.join(
				map(repr, [
					self.project,
					self.route,
					self.type,
					self.symbols,
					self.sources(),
				])
			)
		)

	def __hash__(self):
		if self.project:
			pjid = self.project.factor
		else:
			pjid = None
		return hash((pjid, self.route))

	def __eq__(self, operand):
		return (
			self.project.factor == operand.project.factor and \
			self.route == operand.route
		)

	@property
	def absolute(self):
		return (self.project.factor // self.route)

	@property
	def absolute_path_string(self):
		"""
		# The target's factor path.
		"""
		return '.'.join(self.absolute)

	def __init__(self,
			project:(lsf.Project),
			route:(lsf.types.FactorPath),
			type:(str),
			symbols:(typing.Sequence[str]),
			sources:(typing.Sequence[files.Path]),
			parameters:(typing.Mapping)=None,
			variants:(typing.Mapping)=None,
			method=None,
		):
		self.project = project
		self.route = route
		self.type = type
		self.symbols = symbols
		self._sources = list(sources)
		self.parameters = parameters
		self.method = method

		self.key = None
		self.local_variants = variants or {}

	def __str__(self, struct="({0.type}) {0.name}"):
		return struct.format(self, scheme=self)

	@property
	def name(self):
		try:
			return self.route.identifier
		except:
			# XXX: make route consistent
			return self.route[-1]

	def sources(self):
		"""
		# An iterable producing the source files of the Factor.
		"""
		return self._sources

	def image(self, variants):
		"""
		# Get the appropriate reduction for the Factor based on the
		# configured &key. If no key has been configured, the returned
		# route will be to the inducted factor.
		"""
		return self.project.image(variants, self.route)

class Integrand(tuple):
	"""
	# Container for the set of build parameters used by the configured abstraction functions.
	"""

	mechanism = property(operator.itemgetter(0))
	factor = property(operator.itemgetter(1))
	requirements = property(operator.itemgetter(2))
	dependents = property(operator.itemgetter(3))
	variants = property(operator.itemgetter(4))
	locations = property(operator.itemgetter(5))

	@property
	def operable(self):
		"""
		# Whether the build should be considered operable.
		"""
		for x in self.factor.sources():
			return True
		return False

	@property
	def itype(self):
		return self.factor.type

	@property
	def intention(self) -> str:
		return self.variants.intention

	@property
	def system(self) -> str:
		return self.variants.system

	@property
	def architecture(self) -> str:
		return self.variants.architecture

	@property
	def format(self) -> str:
		return self.variants.get('format') or 'void'

	@property
	def image(self):
		return self.locations['factor-image']

	@staticmethod
	@tools.cachedcalls(8)
	def _qrefs(rfactor, ri):
		tr = lsf.types.Reference.from_ri('type', ri)

		if tr.factor:
			ref = tr.isolate(None)
		else:
			ref = tr.__class__(
				rfactor.project,
				lsf.types.factor@tr.project,
				tr.method, None
			)

		return (ref, tr.isolation)

	def required(self, variants):
		if self.requirements:
			for reqset in self.requirements.values():
				for ri in reqset:
					yield ri.image(variants)

	def select(self, field):
		"""
		# Retrieve information from requirements and components.
		"""
		if field in self.locations:
			yield self.locations[field]
			return

		if field in self.factor.fields:
			yield self.factor.get(field)
			return

		# Presume requirement query at this point.
		try:
			ref, rfield = self._qrefs(self.factor.type, field)
		except Exception:
			return

		if self.requirements:
			if rfield in {'factor-image', 'factor-image-name'}:
				# Special case image as it requires variants.
				if rfield.endswith('-name'):
					for r in self.requirements.get(ref, ()):
						yield r.image(self.variants).identifier
				else:
					for r in self.requirements.get(ref, ()):
						yield r.image(self.variants)
			else:
				for r in self.requirements.get(ref, ()):
					yield r.get(rfield)
