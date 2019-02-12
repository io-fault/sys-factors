"""
# Core classes and data structures for building projects with Construction Contexts.
"""
import typing
import functools
import itertools
import importlib
import operator

from fault.hkp import library as libhkp
from fault.routes import library as libroutes
from fault.project import library as libproject
from fault.system import files
from fault.system import python

from . import data

fpi_addressing = libhkp.Hash('fnv1a_32', depth=1, length=2)

def context_interface(path):
	"""
	# Resolves the construction interface for processing a source or performing
	# the final reduction (link-stage).
	"""

	# Avoid at least one check as it is known there is at least
	# one attribute in the path.
	leading, final = path.rsplit('.', 1)
	mod, apath = python.Import.from_attributes(leading)
	obj = importlib.import_module(str(mod))

	for x in apath:
		obj = getattr(obj, x)

	return getattr(obj, final)

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
		url = i.identifier
		return '{1}{0}:{2}'.format(url, i.icon or '', self.route)

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
						sf_route = files.Path.from_absolute(sf_int)
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

class Mechanism(object):
	"""
	# The mechanics used to produce an Integral from a set of Sources associated
	# with a Factor. &Mechanism instances are usually created by &Context instances
	# using &Context.select.

	# [ Properties ]

	# /descriptor/
		# The data structure referring to the interface used
		# to construct processing instructions for the selected mechanism.
	# /cache/
		# Mapping of resolved adapters. Used internally for handling
		# adapter inheritance.
	"""

	def __init__(self, descriptor):
		self.descriptor = descriptor
		self.cache = {}

	@property
	def symbol(self):
		return self.descriptor['path'][0]

	@property
	def groups(self):
		return self.descriptor['groups']

	@property
	def integrations(self):
		return self.descriptor['integrations']

	@property
	def transformations(self):
		return self.descriptor['transformations']

	def integrates(self):
		ints = self.descriptor.get('integrations')
		if ints:
			return True
		else:
			return False

	def suffix(self, factor):
		"""
		# Return the suffix that the given factor should use for its integral.
		"""
		tfe = self.descriptor.get('target-file-extensions', {None: '.v'})
		return (
			tfe.get(factor.type) or \
			tfe.get(None) or '.i'
		)

	def prepare(self, build):
		"""
		# Generate any requisite filesystem requirements.
		"""

		loc = build.locations
		f = build.factor
		ftr = loc['integral']

		yield ('directory', None, None, (None, ftr.container))

		od = loc['output']
		ld = loc['log']
		emitted = set((od, ld))

		for src in f.sources():
			outfile = files.Path(od, src.points)
			logfile = files.Path(ld, src.points)

			for x in (outfile, logfile):
				d = x.container
				emitted.add(d)

		for x in emitted:
			if not x.exists():
				yield ('directory', None, None, (None, x))

	def adaption(self, build, domain, source, phase='transformations'):
		"""
		# Select the adapter of the mechanism for the given source.

		# Adapters with inheritance will be cached by the mechanism.
		"""
		acache = self.cache
		aset = self.descriptor[phase]

		# Mechanisms support explicit inheritance.
		if (phase, domain) in acache:
			return acache[(phase, domain)]

		if domain in aset:
			key = domain
		else:
			# For transformations, usually a compiler collection.
			# Integrations usually only consist of one.
			key = None

		lmech = aset[key]
		layers = [lmech]
		while 'inherit' in (lmech or ()):
			basemech = lmech['inherit']
			layers.append(aset[basemech]) # mechanism inheritance
			lmech = aset[basemech]
		layers.reverse()

		cmech = {}
		for x in layers:
			if x is not None:
				data.merge(cmech, x)
		cmech.pop('inherit', None)

		# cache merged mechanism
		acache[(phase, domain)] = cmech

		return cmech

	def transform(self, build, filtered):
		"""
		# Transform the sources using the mechanisms defined in &context.
		"""

		f = build.factor
		fdomain = f.domain
		loc = build.locations
		logs = loc['log']
		intention = build.context.intention
		fmt = build.variants['format']

		mechanism = build.mechanism.descriptor
		ignores = mechanism.get('ignore-extensions', ())

		commands = []
		for src in f.sources():
			fnx = src.extension
			if intention != 'fragments' and fnx in ignores or src.identifier.startswith('.'):
				# Ignore header files and dot-files for non-delineation contexts.
				continue
			obj = files.Path(loc['output'], src.points)

			if filtered((obj,), (src,)):
				continue

			logfile = files.Path(loc['log'], src.points)

			src_type = build.context.language(src.extension)
			out_format = mechanism['formats'][f.type]

			adapter = self.adaption(build, src_type, src, phase='transformations')
			if 'interface' in adapter:
				xf = context_interface(adapter['interface'])
			else:
				sys.stdout.write('[!# ERROR: no interface for transformation %r %s]\n' % (src_type, str(src)))
				continue

			# Compilation to out_format for integration.
			seq = list(xf(build, adapter, out_format, obj, src_type, (src,)))

			yield self.formulate(obj, (src,), logfile, adapter, seq)

	def formulate(self, route, sources, logfile, adapter, sequence):
		"""
		# Convert a generated instruction into a form accepted by &Construction.
		"""

		method = adapter.get('method')
		command = adapter.get('command')
		redirect = adapter.get('redirect')

		if method == 'python':
			# XXX: Force tool to resolve proper executable.
			import sys
			sequence[0:1] = (sys.executable, '-m', command)
		elif method == 'internal':
			return ('call', sequence, logfile, (sources, route))
		else:
			# Adapter interface leaves this as None or a relative name.
			# Update to absolute path entered into adapter.
			sequence[0] = command

		if redirect == 'io':
			return ('execute-stdio', sequence, logfile, (sources, route))
		elif redirect:
			return ('execute-redirection', sequence, logfile, (sources, route))
		else:
			# No redirect.
			return ('execute', sequence, logfile, (sources, route))

	def integrate(self, transform_mechs, build, filtered):
		"""
		# Construct the operations for reducing the object files created by &transform
		# instructions into a set of targets that can satisfy
		# the set of dependents.
		"""

		f = build.factor
		loc = build.locations
		mechanism = build.mechanism.descriptor

		fmt = build.variants.get('format')
		if fmt is None:
			return
		if 'integrations' not in mechanism:# or f.reflective: XXX
			# warn/note?
			return

		mechp = mechanism
		ftr = loc['integral']
		rr = ftr

		# Discover the known sources in order to identify which objects should be selected.
		objdir = loc['output']
		sources = set([
			x.points for x in f.sources()
			if x.extension not in mechp.get('ignore-extensions', ())
		])
		objects = [
			objdir.__class__(objdir, x) for x in sources
		]

		if build.requirements:
			partials = [x for x in build.requirements[(f.domain, 'partial')]]
		else:
			partials = ()

		# XXX: does not account for partials
		if filtered((rr,), objects):
			return

		adapter = self.adaption(build, f.type, objects, phase='integrations')

		# Mechanisms with a configured root means that the
		# transformed objects will be referenced by the root file.
		root = adapter.get('root')
		if root is not None:
			objects = [objdir / root]

		# Libraries and partials of the same domain are significant.
		if build.requirements:
			libraries = [x for x in build.requirements[(f.domain, 'library')]]
		else:
			libraries = ()

		xf = context_interface(adapter['interface'])
		seq = xf(transform_mechs, build, adapter, f.type, rr, fmt, objects, partials, libraries)
		logfile = loc['log'] / 'Integration.log'

		yield self.formulate(rr, objects, logfile, adapter, seq)

class Build(tuple):
	"""
	# Container for the set of build parameters used by the configured abstraction functions.
	"""
	context = property(operator.itemgetter(0))
	mechanism = property(operator.itemgetter(1))
	factor = property(operator.itemgetter(2))
	requirements = property(operator.itemgetter(3))
	dependents = property(operator.itemgetter(4))
	variants = property(operator.itemgetter(5))
	locations = property(operator.itemgetter(6))
	parameters = property(operator.itemgetter(7))
	environment = property(operator.itemgetter(8))

	def required(self, domain, ftype):
		ctx = self.context
		needed_variants = ctx.variants(domain, ftype)

		reqs = self.requirements.get((domain, ftype), ())

		srcvars = ctx.index['source']['variants']
		for x in reqs:
			if isinstance(x, SystemFactor):
				yield x.integral(), x
				continue

			v = {'name': x.name}
			v.update(needed_variants)
			g = ctx.groups(x.project.environment)
			path = x.integral(g, v)
			yield path, x
