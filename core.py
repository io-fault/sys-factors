"""
# Core classes and data structures for building projects with Construction Contexts.
"""
import typing
import functools
import itertools
import importlib
import operator

from fault.project import root
from fault.project import types as project_types
from fault.system import files
from fault.system import python

from . import data

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
			type = 'source-tree',
			name = None,
			integral = path
		)

	@classmethod
	def library(Class, path, name, domain='host'):
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
							image = sf_route,
							name = sf_name
						)

	def __init__(self, **kw):
		for k in ('sources', 'image'):
			v = kw.pop(k, None)
			kw['_'+k] = v

		self.__dict__.update(kw)

	def sources(self):
		return self.__dict__['_sources']

	def image(self):
		return self.__dict__['_image']
	integral = image

	@property
	def symbols(self):
		return {}

class Target(object):
	"""
	# The representation of a Project Factor as a compilation target.
	"""

	default_build_name = '__build__'

	def __repr__(self):
		return "<%s:%s>" %(self.type, self.route)

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
		return hash((self.project.factor, self.route))

	def __eq__(self, operand):
		return (
			self.project.factor == operand.project.factor and \
			self.route == operand.route
		)

	@property
	def absolute(self):
		return (self.project.factor + self.route)

	@property
	def absolute_path_string(self):
		"""
		# The target's factor path.
		"""
		return '.'.join(self.absolute)

	def __init__(self,
			project:(root.Project),
			route:(root.types.FactorPath),
			domain:(str),
			type:(str),
			symbols:(typing.Sequence[str]),
			sources:(typing.Sequence[files.Path]),
			parameters:(typing.Mapping)=None,
			variants:(typing.Mapping)=None,
			intention=None,
		):
		self.project = project
		self.route = route
		self.domain = domain
		self.type = type
		self.symbols = symbols
		self._sources = list(sources)
		self.parameters = parameters
		self.intention = intention

		self.key = None
		self.local_variants = variants or {}

	def __str__(self, struct="({0.domain}.{0.type}) {0.name}"):
		return struct.format(self, scheme=self)

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

	def work_key(self, *variant_sets, **variants):
		# Combine variants.
		vl = list(itertools.chain.from_iterable(v.items() for v in variant_sets))
		vl.extend(self.local_variants.items())
		vl.extend(variants.items())

		# Eliminate duplicates.
		vl = list(dict(vl).items())
		vl.sort()
		vars = ';'.join('='.join((k, str(v))) for k, v in vl)

		return vl, vars.encode('utf-8')

	def image(self, variants, overrides=None):
		"""
		# Get the appropriate reduction for the Factor based on the
		# configured &key. If no key has been configured, the returned
		# route will be to the inducted factor.
		"""

		if overrides is not None:
			variants.update(overrides)

		if self.intention is not None:
			# Variant (image) intention override for requirements.
			# For Contexts like delineation, the requirements need
			# a real image. Notably, for source factors such as C headers.
			variants['intention'] = self.intention

		return self.project.image(variants, self.route)
	integral = image

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
			yield fformats.get(self.type)

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

		for fmt in self.formats(mechanism, dependents):
			yield [], self.work_key(dict(variants), format=fmt)

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
			if x.fs_type() == 'void':
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
			out_format = mechanism['formats'][f.type] # No format description for factor type?

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
		# Construct the operations for reducing the transformations.
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
		logfile = loc['log'] / 'Integration'

		yield self.formulate(rr, objects, logfile, adapter, seq)

class Build(tuple):
	"""
	# Container for the set of build parameters used by the configured abstraction functions.
	"""
	context = property(operator.itemgetter(0)) # Construction Context
	mechanism = property(operator.itemgetter(1))
	factor = property(operator.itemgetter(2))
	requirements = property(operator.itemgetter(3))
	dependents = property(operator.itemgetter(4))
	variants = property(operator.itemgetter(5))
	locations = property(operator.itemgetter(6))
	parameters = property(operator.itemgetter(7))
	environment = property(operator.itemgetter(8))

	def required(self, ftype):
		ctx = self.context
		domain = ctx.identify(ftype)
		needed_variants = ctx.variants(domain, ftype)

		reqs = self.requirements.get((domain, ftype), ())
		for x in reqs:
			if isinstance(x, SystemFactor):
				yield x.image(), x
			else:
				v = dict(needed_variants)
				v['name'] = x.name
				path = x.image(v)
				yield path, x

	@property
	def system(self):
		return self.variants.get('system', 'void')
