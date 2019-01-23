"""
# Core classes and data structures for building projects with Construction Contexts.
"""
import typing
import functools
import itertools

from fault.hkp import library as libhkp
from fault.routes import library as libroutes
from fault.project import library as libproject
from fault.system import files

fpi_addressing = libhkp.Hash('fnv1a_32', depth=1, length=2)

class Project(object):
	"""
	# Project Information and Infrastructure storage.
	# Provides Construction Contexts with project identity and
	# the necessary data for resolving infrastructure symbols.

	# [ Properties ]
	# /infrastructure/
		# The infrastructure symbols provided by the project.
	# /information/
		# The finite map extracted from the &source.
	"""

	def __hash__(self):
		return hash(str(self.paths.project))

	@property
	def symbol(self):
		i = self.information
		url = i['identifier']
		return '[{1}{0}]:{2}'.format(url, i['icon'].get('emoji', ''), self.route)

	@property
	def segment(self):
		"""
		# Return the factor path of the Project.
		"""
		return libroutes.Segment(None, (self.paths.root >> self.paths.project)[1])

	@property
	def route(self):
		return self.paths.project

	@property
	def product(self):
		"""
		# The route to the parent directory of the context, category, or project.
		"""
		p = self.paths
		base = p.context or p.category or p.project
		return base.container

	@property
	def environment(self):
		"""
		# Path to the environment containing the project.
		"""

		current = self.product.container
		while not (current/'.environment').exists():
			current = current.container
			if str(current) == '/':
				break
		else:
			return current

		return None

	def __init__(self, paths, infrastructure, information):
		self.paths = paths
		self.information = information
		self.infrastructure = infrastructure

class SystemFactor(object):
	"""
	# Factor structure used to provide access to include and library directories.
	# Instances are normally stored in &Build.requirements which is populated by
	# the a factor's requirements list.
	"""

	@classmethod
	def headers(Class, path):
		return Class(
			domain = 'source',
			type = 'library',
			name = None,
			integral = path
		)

	@classmethod
	def library(Class, path, name, domain='system'):
		return Class(
			domain = domain,
			type = 'library',
			integral = path,
			name = name,
		)

	@property
	def pair(self):
		return (self.domain, self.type)

	@property
	def absolute(self):
		# XXX: invariant
		return ()

	@classmethod
	def collect(Class, tree):
		"""
		# Create set of SystemFactor's from a nested dictionary of definitions.
		"""
		for domain, types in tree.items():
			for ft, sf in types.items():
				for sf_int in sf:
					if sf_int is not None:
						sf_route = system_files.Path.from_absolute(sf_int)
					else:
						sf_route = None

					for sf_name in sf[sf_int]:
						yield SystemFactor(
							domain = domain,
							type = ft,
							integral = sf_route,
							name = sf_name
						)

	def __init__(self, **kw):
		for k in ('sources', 'integral'):
			v = kw.pop(k, None)
			kw['_'+k] = v

		self.__dict__.update(kw)

	def sources(self):
		return self.__dict__['_sources']

	def integral(self, *ignored):
		return self.__dict__['_integral']

class Target(object):
	"""
	# A Factor of a project; conceptually similar to "targets" in IDEs.
	# &Factor instances are specific to the module-local Construction Context
	# implementation.

	# Initialized with the primary dependencies of most operations to avoid
	# redundancy and in order to allow simulated factors to be managed without
	# modifying or cleaning up &sys.modules.

	# [ Properties ]
	# /local_variants/
		# Explicitly designated variants.
	"""

	default_cache_name = '__f-cache__'
	default_integral_name = '__f-int__'

	def __repr__(self):
		return "<%s>" %('.'.join(self.route),)

	def __r_repr__(self):
		return "{0.__class__.__name__}({1})".format(
			self,
			', '.join(
				map(repr, [
					self.project,
					self.route,
					self.domain,
					self.type,
					self.symbols,
					self.sources(),
				])
			)
		)

	def __hash__(self):
		return hash(self.absolute)

	@property
	def absolute(self):
		return (self.project.segment.extend(self.route))

	@property
	def absolute_path_string(self):
		"""
		# The target's factor path.
		"""
		return '.'.join(self.absolute)

	def __eq__(self, ob):
		return self.absolute == ob.absolute

	def __init__(self,
			project:(Project),
			route:(libroutes.Segment),
			domain:(str),
			type:(str),
			symbols:(typing.Sequence[str]),
			sources:(typing.Sequence[libroutes.Route]),
			parameters:(typing.Mapping)=None,
			variants:(typing.Mapping)=None,
		):
		"""
		# Either &route or &module can be &None, but not both. The system's
		# &importlib will be used to resolve a module from the &route in its
		# absence, and the module's (python/attribute)`__name__` field will
		# be used to construct the &Import route given &route's absence.
		"""
		self.project = project
		self.route = route
		self.domain = domain
		self.type = type
		self.symbols = symbols
		self._sources = sources
		self.parameters = parameters

		self.key = None
		self.local_variants = variants or {}

	def __str__(self, struct="({0.domain}.{0.type}) {0.name}"):
		return struct.format(self, scheme=self.type[:3])

	@property
	def name(self):
		try:
			return self.route.identifier
		except:
			# XXX: make route consistent
			return self.route[-1]

	@property
	def pair(self):
		return (self.domain, self.type)

	def sources(self):
		"""
		# An iterable producing the source files of the Factor.
		"""
		return self._sources

	@property
	def cache_directory(self) -> files.Path:
		"""
		# Factor build cache directory.
		"""
		p = self.project.paths.project.extend(self.route)
		if p.is_directory():
			return p / self.default_cache_name
		else:
			return p.container / self.default_cache_name

	@property
	def fpi_root(self) -> files.Path:
		"""
		# Factor Processing Instruction root work directory for the given Factor, &self.
		"""
		return self.cache_directory

	@staticmethod
	def fpi_work_key(variants):
		"""
		# Calculate the key from the sorted list.

		# Sort function is of minor importance, there is no warranty
		# of consistent accessibility across platform.
		"""
		return ';'.join('='.join((k,v)) for k,v in variants).encode('utf-8')

	def fpi_initialize(self, groups, *variant_sets, **variants):
		"""
		# Update and return the dictionary key used to access the processed factor.
		"""

		vl = list(itertools.chain.from_iterable(v.items() for v in variant_sets))
		vl.extend(self.local_variants.items())
		vl.extend(variants.items())
		vl = list(dict(vl).items())
		vl.sort()
		variants = dict(vl)

		key = self.fpi_work_key(vl)
		wd = self.fpi_set.route(key, filename=str)

		i = libproject.integrals(self.project.route, self.route)
		out = libproject.compose_integral_path(variants, groups=groups)
		out = i.extend(out).suffix('.i')

		return vl, key, {
			'integral': out,
			'work': wd,
			'libraries': wd / 'lib',
			'log': wd / 'log',
			'output': wd / 'xfd',
			'sources': wd / 'src',
		}

	@property
	@functools.lru_cache(32)
	def fpi_set(self) -> libhkp.Dictionary:
		"""
		# &libhkp.Dictionary containing the builds of different variants.
		"""
		fr = self.fpi_root
		wd = libhkp.Dictionary.use(fr, addressing=fpi_addressing)
		return wd

	def fpi_work_exists(self, key):
		"""
		# Get the work directory of the Factor for the given variants.
		"""

		return self.fpi_set.has_key(key)

	def integral(self, groups, variants):
		"""
		# Get the appropriate reduction for the Factor based on the
		# configured &key. If no key has been configured, the returned
		# route will be to the inducted factor.
		"""

		i = libproject.integrals(self.project.route, self.route)
		path = libproject.compose_integral_path(variants, groups=groups)
		i = i.extend(path)

		return i.suffix('.i')

	def formats(self, mechanism, dependents):
		"""
		# Yield the formats to build based on the given mechanism, dependents and
		# the factor's type.

		# For factors other than `'partial'`, this is always a single item.
		"""

		fformats = mechanism.descriptor['formats'] # code types used by the object types

		if self.type == 'partial':
			# For partials, the dependents decide
			# the format set to build. If no format is designated,
			# the default is presumed.
			default = fformats.get('partial') or fformats[None]

			for x in dependents:
				yield fformats.get(x.type, default)
		else:
			# For system factors, this determines PIC/PIE/Unspecified.
			yield fformats.get(self.type) or fformats[None]

	def groups(self, context):
		return context.groups(self.project.environment)

	def link(self, variants, context, mechanism, reqs, dependents):
		"""
		# Generate the variants, source parameters, and locations used
		# to perform a build.

		# [ Parameters ]
		# /context/
			# &Context instance providing the required mechanisms.
		# /mechanism/
			# &Mechanism selected for production of the Factor Processing Instructions.
		# /reqs/
			# The dependencies, composite factors, specified by imports.
		# /dependents/
			# The list of Factors depending on this target.
		"""

		groups = self.groups(context)

		for fmt in self.formats(mechanism, dependents):
			vars = dict(variants)
			vars['format'] = fmt

			yield [], self.fpi_initialize(groups, vars, format=fmt)
