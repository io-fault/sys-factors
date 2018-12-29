"""
# Construction Context implementation in Python.

# [ Engineering ]
# /Mechanism Load Order/
	# Mechanism data layers are not merged in a particular order.
	# This allows for inconsistencies to occur across &Context instances.
"""
import os
import sys
import functools
import itertools
import collections
import contextlib
import operator
import importlib
import importlib.machinery
import types
import typing
import pickle
import copy

from . import include

from fault.computation import library as libc
from fault.time import library as libtime
from fault.routes import library as libroutes
from fault.io import library as libio
from fault.system import library as libsys
from fault.system import libfactor
from fault.system import python as system_python
from fault.system import files as system_files
from fault.filesystem import library as libfs
from fault.text import struct as libstruct
from fault.project import library as libproject
from fault.internet import ri

File = system_files.Path
fpi_addressing = libfs.Hash('fnv1a_32', depth=1, length=2)

def update_named_mechanism(route:File, name:str, data):
	"""
	# Given a route to a mechanism file in a construction context,
	# overwrite the file's mechanism entry with the given &data.

	# [ Parameters ]
	# /route/
		# The route to the file that is to be modified.
	# /name/
		# The component in the mechanism file to replace.
	# /data/
		# The dictionary to set as the mechanism's content.
	"""

	if route.exists():
		stored = pickle.loads(route.load())
	else:
		stored = {}

	stored[name] = data
	route.store(pickle.dumps(stored))

def load_named_mechanism(route:File, name:str):
	"""
	# Given a route to a mechanism file in a construction context,
	# load the file's mechanism entry.

	# [ Parameters ]
	# /route/
		# The route to the mechanisms 
	"""
	return pickle.loads(route.load())[name]

import faulthandler
faulthandler.enable()

def context_interface(path):
	"""
	# Resolves the construction interface for processing a source or performing
	# the final reduction (link-stage).
	"""

	# Avoid at least one check as it is known there is at least
	# one attribute in the path.
	leading, final = path.rsplit('.', 1)
	mod, apath = system_python.Import.from_attributes(leading)
	obj = importlib.import_module(str(mod))

	for x in apath:
		obj = getattr(obj, x)

	return getattr(obj, final)

def rebuild(outputs, inputs, subfactor=True, cascade=False):
	"""
	# Unconditionally report the &outputs as outdated.
	"""
	if cascade is False and subfactor is False:
		# If rebuild is selected, &cascade must be enabled in order
		# for out-of-selection factors to be rebuilt.
		return True

	return False

def updated(outputs, inputs, never=False, cascade=False, subfactor=True):
	"""
	# Return whether or not the &outputs are up-to-date.

	# &False returns means that the target should be reconstructed,
	# and &True means that the file is up-to-date and needs no processing.
	"""

	if never:
		# Never up-to-date.
		if cascade:
			# Everything gets refreshed.
			return False
		elif subfactor:
			# Subfactor inherits never regardless of cascade.
			return False

	olm = None
	for output in outputs:
		if not output.exists():
			# No such object, not updated.
			return False
		lm = output.get_last_modified()
		olm = min(lm, olm or lm)

	# Otherwise, check the inputs against outputs.
	# In the case of a non-cascading rebuild, it is desirable
	# to perform the input checks.

	for x in inputs:
		if not x.exists() or x.get_last_modified() > olm:
			# rebuild if any output is older than any source.
			return False

	# object has already been updated.
	return True

def group(factors:typing.Sequence[object]):
	"""
	# Organize &factors by their domain-type pair using (python/attribute)`pair` on
	# the factor.
	"""

	container = collections.defaultdict(set)
	for f in factors:
		container[f.pair].add(f)
	return container

def interpret_reference(index, factor, symbol, url):
	"""
	# Extract the project identifier from the &url and find a corresponding
	# entry in the project set, &index.

	# The fragment portion of the URL specifies the factor within the project
	# that should be connected in order to use the &symbol.
	"""

	print(url, index)
	i = ri.parse(url)
	rfactor = i.pop('fragment', None)
	rproject_name = i['path'][-1]

	i['path'][-1] = '' # Force the trailing slash in serialize()
	product = ri.serialize(i)

	project = None
	path = None
	ftype = (None, None)
	rreqs = {}
	sources = []

	project_url = product + rproject_name

	project = Project(*index.select(project_url))
	factor = libroutes.Segment.from_sequence(rfactor.split('.'))
	factor_dir = project.route.extend(factor.absolute)
	from fault.project import explicit
	ctx, data = explicit.struct.parse((factor_dir/'factor.txt').get_text_content())

	t = Target(project, factor, data['domain'] or 'system', data['type'], rreqs, [])
	return t

def requirements(index, symbols, factor):
	"""
	# Return the set of factors that is required to build this Target, &self.
	"""

	if isinstance(factor, SystemFactor): # XXX: eliminate variation
		return

	for sym, refs in factor.symbols.items():
		if sym in symbols:
			sdef = symbols[sym]
			if isinstance(sdef, list):
				yield from sdef
			else:
				yield from SystemFactor.collect(symbols[sym])
			continue

		for r in refs:
			if isinstance(r, Target):
				yield r
			else:
				yield interpret_reference(index, factor, sym, r)

def resolve(infrastructure, overrides, symbol):
	if symbol in overrides:
		return overrides[symbol]
	return infrastructure[symbol]

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

	default_cache_name = '__f_cache__'
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
	def cache_directory(self) -> File:
		"""
		# Factor build cache directory.
		"""
		p = self.project.paths.project.extend(self.route)
		if p.is_directory():
			return p / self.default_cache_name
		else:
			return p.container / self.default_cache_name

	@property
	def fpi_root(self) -> File:
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
		out = libproject.compose(groups, variants)
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
	def fpi_set(self) -> libfs.Dictionary:
		"""
		# &libfs.Dictionary containing the builds of different variants.
		"""
		fr = self.fpi_root
		wd = libfs.Dictionary.use(fr, addressing=fpi_addressing)
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
		path = libproject.compose(groups, variants)
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

merge_operations = {
	set: set.update,
	list: list.extend,
	int: int.__add__,
	tuple: (lambda x, y: x + tuple(y)),
	str: (lambda x, y: y), # override strings
	tuple: (lambda x, y: y), # override tuple sequences
	None.__class__: (lambda x, y: y),
}

def merge(parameters, source, operations = merge_operations):
	"""
	# Merge the given &source into &parameters applying merge functions
	# defined in &operations. Dictionaries are merged using recursion.
	"""
	for key in source:
		if key in parameters:
			# merge parameters by class
			cls = parameters[key].__class__
			if cls is dict:
				merge_op = merge
			else:
				merge_op = operations[cls]

			# DEFECT: The manipulation methods often return None.
			r = merge_op(parameters[key], source[key])
			if r is not None and r is not parameters[key]:
				parameters[key] = r
		else:
			parameters[key] = source[key]

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
			outfile = File(od, src.points)
			logfile = File(ld, src.points)

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
				merge(cmech, x)
		cmech.pop('inherit', None)

		# cache merged mechanism
		acache[(phase, domain)] = cmech

		return cmech

	def transform(self, build, filtered=rebuild):
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
			obj = File(loc['output'], src.points)

			if filtered((obj,), (src,)):
				continue

			logfile = File(loc['log'], src.points)

			src_type = build.context.language(src.extension)
			out_format = mechanism['formats'][f.type]

			adapter = self.adaption(build, src_type, src, phase='transformations')
			if 'interface' in adapter:
				print('transform', src)
				xf = context_interface(adapter['interface'])
			else:
				print('no interface for transformation', src_type, str(src))
				continue

			# Compilation to out_format for integration.
			seq = list(xf(build, adapter, out_format, obj, src_type, (src,)))

			yield self.formulate(obj, (src,), logfile, adapter, seq)

	def formulate(self, route, sources, logfile, adapter, sequence, python=sys.executable):
		"""
		# Convert a generated instruction into a form accepted by &Construction.
		"""

		method = adapter.get('method')
		command = adapter.get('command')
		redirect = adapter.get('redirect')

		if method == 'python':
			sequence[0:1] = (python, '-m', command)
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

	def integrate(self, transform_mechs, build, filtered=rebuild, sys_platform=sys.platform):
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

		print('integrate', str(f))
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

class Context(object):
	"""
	# A collection of mechanism sets and parameters used to construct processing instructions.

	# [ Engineering ]
	# This class is actually a Context implementation and should be relocated
	# to make room for a version that interacts with an arbitrary context
	# for use in scripts that perform builds. Direct use is not actually
	# intended as it's used to house the mechanisms.
	"""

	@staticmethod
	def systemfactors(ifactors) -> typing.Iterator[SystemFactor]:
		"""
		# Load the system factors in the parameters file identified by &sf_name.
		"""

		for domain, types in ifactors.items():
			for ft, sf in types.items():
				for sf_int in sf:
					if sf_int is not None:
						sf_route = File.from_absolute(sf_int)
					else:
						sf_route = None

					for sf_name in sf[sf_int]:
						yield SystemFactor(
							domain = domain,
							type = ft,
							integral = sf_route,
							name = sf_name
						)

	def __init__(self, sequence, symbols):
		self.sequence = sequence or ()
		self.symbols = symbols
		self._languages = {}

		self.index = dict()
		for mid, slots in self.sequence:
			for name, data in slots.items():
				merge(self.index, data)

		syntax = self.index.get('syntax')
		if syntax:
			s = syntax.get('target-file-extensions')
			for pl, exts in s.items():
				for x in exts.split(' '):
					self._languages[x] = pl

	def variants(self, domain, ftype):
		"""
		# Get the variants associated with the domain using the cached view provided by &select.
		"""
		return self.select(domain)[0]

	@functools.lru_cache(8)
	def groups(self, environment) -> typing.Sequence[typing.Sequence[str]]:
		"""
		# Parse and cache the contents of the (filename)`groups.txt` file in the
		# &environment route.

		# This is the context's perspective; effectively consistent across reads
		# due to the cache. If no (filename)`groups.txt` is found, the
		# default (format)`system-architecture/name` is returned.
		"""

		if environment is None:
			return [['system', 'architecture'], ['name']]

		gtxt = environment / '.environment' / 'groups.txt'
		if gtxt.exists():
			groups = list(libproject.parse_integral_descriptor_1(gtxt.get_text_content()))
		else:
			# No groups.txt file.
			groups = [['system', 'architecture'], ['name']]

		return groups

	def extrapolate(self, factors):
		"""
		# Rewrite factor directories into sets of specialized domain factors.
		# Query implementations have no knowledge of specialized domains. This
		# method interprets the files in those directories and creates a proper
		# typed factor for the source.
		"""
		ftype = 'library'

		for path, files in factors:
			for f in files[-1]:
				# Split from left to capture name.
				try:
					stem, suffix = f.identifier.split('.', 1)
				except ValueError:
					stem = f.identifier
					suffix = None
					# XXX: data factor
					continue

				# Find domain.
				try:
					domain = self.language(suffix)
				except:
					# XXX: map to void domain indicating/warning about unprocessed factor?
					continue

				yield (libroutes.Segment(None, path + (stem,)), (domain, ftype, [f]))

	def language(self, extension):
		"""
		# Syntax domain query selecting the language associated with a file extension.
		"""
		return self._languages.get(extension, 'void')

	@property
	def name(self):
		"""
		# The context name identifying the target architectures.
		"""
		return self.index['context']['name']

	@property
	def intention(self):
		return self.index['context']['intention']

	@functools.lru_cache(8)
	def select(self, fdomain):
		# Scan the paths (loaded data sets) for the domain.
		variants = {'intention': self.intention}

		if fdomain in self.index:
			mechdata = copy.deepcopy(self.index[fdomain])
			variants.update(mechdata.get('variants', ()))

			if 'inherit' in mechdata:
				# Recursively merge inherit's.
				inner = mechdata['inherit']
				ivariants, imech = self.select(inner)
				merge(mechdata, imech.descriptor)
				variants.update(ivariants)
				mechdata['path'] = [fdomain] + mechdata['path']
			else:
				mechdata['path'] = [fdomain]

			mech = Mechanism(mechdata)
		else:
			# Unsupported domain.
			mech = Mechanism(self.index['void'])
			mech.descriptor['path'] = [fdomain]

		print(mech.descriptor['path'])
		return variants, mech

	@functools.lru_cache(16)
	def field(self, path, prefix):
		"""
		# Retrieve a field from the set of mechanisms.
		"""
		domain, *start = prefix.split('/')
		variants, cwd = self.select(domain)
		for key in start:
			cwd = cwd[key]
		for key in path.split('/'):
			cwd = cwd[key]
		return cwd

	def __bool__(self):
		"""
		# Whether the Context has any mechanisms.
		"""
		return bool(self.sequence)

	@staticmethod
	def load(route:File):
		for x in route.files():
			yield x.identifier, pickle.loads(x.load())

	@classmethod
	def from_environment(Class, envvar='FPI_MECHANISMS'):
		mech_refs = os.environ.get(envvar, '').split(os.pathsep)
		seq = []
		for mech in mech_refs:
			mech = File.from_absolute(mech)
			seq.extend(list(Class.load(mech)))

		ctx = File.from_absolute(os.environ.get('CONTEXT'))
		r = Class(seq, dict(Class.load(ctx/'symbols')))
		return r

	@classmethod
	def from_directory(Class, route):
		syms = (route / 'symbols')
		mechs = Class.load(route/'mechanisms')

		return Class(list(mechs), dict(Class.load(syms)))

def traverse(descent, working, tree, inverse, node):
	"""
	# Invert the directed graph of dependencies from the node.
	"""

	deps = set(descent(node))

	if not deps:
		# No dependencies, add to working set and return.
		working.add(node)
		return
	elif node in tree:
		# It's already been traversed in a previous run.
		return

	# dependencies present, assign them inside the tree.
	tree[node] = deps

	for x in deps:
		# Note the factor as depending on &x and build
		# its tree.
		inverse[x].add(node)
		traverse(descent, working, tree, inverse, x)

def sequence(descent, nodes, defaultdict=collections.defaultdict, tuple=tuple):
	"""
	# Generator maintaining the state of the sequencing of a traversed depedency
	# graph. This generator emits factors as they are ready to be processed and receives
	# factors that have completed processing.

	# When a set of dependencies has been processed, they should be sent to the generator
	# as a collection; the generator identifies whether another set of modules can be
	# processed based on the completed set.

	# Completion is an abstract notion, &sequence has no requirements on the semantics of
	# completion and its effects; it merely communicates what can now be processed based
	# completion state.
	"""

	reqs = dict()
	tree = dict() # dependency tree; F -> {DF1, DF2, ..., DFN}
	inverse = defaultdict(set)
	working = set()

	for node in nodes:
		traverse(descent, working, tree, inverse, node)

	new = working
	# Copy tree.
	for x, y in tree.items():
		cs = reqs[x] = defaultdict(set)
		for f in y:
			cs[f.pair].add(f)

	yield None

	while working:
		for x in new:
			if x not in reqs:
				reqs[x] = defaultdict(set)

		completion = (yield tuple(new), reqs, {x: tuple(inverse[x]) for x in new if inverse[x]})
		for x in new:
			reqs.pop(x, None)
		new = set() # &completion triggers new additions to &working

		for node in (completion or ()):
			# completed.
			working.discard(node)

			for deps in inverse[node]:
				tree[deps].discard(node)
				if not tree[deps]:
					# Add to both; new is the set reported to caller,
					# and working tracks when the graph has been fully sequenced.
					new.add(deps)
					working.add(deps)

					del tree[deps]

def disabled(*args, **kw):
	"""
	# A transformation that can be assigned to a subject's mechanism
	# in order to describe it as being disabled.
	"""
	return ()

def transparent(build, adapter, o_type, output, i_type, inputs, verbose=True):
	"""
	# Create links from the input to the output; used for zero transformations.
	"""

	input, = inputs # Rely on exception from unpacking; expecting one input.
	return [None, '-f', input, output]

def void(build, adapter, o_type, output, i_type, inputs, verbose=True):
	"""
	# Command constructor executing &.bin.void with the intent of emitting
	# an error designating that the factor could not be processed.
	"""
	return [None, output] + list(inputs)

def standard_io(build, adapter, o_type, output, i_type, inputs, verbose=True):
	"""
	# Interface returning a command with no arguments.
	# Used by transformation mechanisms that operate using standard I/O.
	"""
	return [None]

def standard_out(build, adapter, o_type, output, i_type, inputs, verbose=True, root=False):
	"""
	# Takes the set of files as the initial parameters and emits
	# the processed result to standard output.
	"""

	return [None] + list(inputs)

def package_module_parameter(build, adapter, o_type, output, i_type, inputs,
		verbose=True,
		root=False,
		filepath=str,
	):
	"""
	# Reconstruct the qualified module path from the inputs and
	# the build's factor route.
	"""
	f = build.factor
	ir = f.route

	src, = inputs
	modname = src.identifier[:-3]
	if modname != '__init__':
		modpath = ir / modname
	else:
		modpath = ir

	return [None, str(modpath)]

def concatenation(build, adapter, o_type, output, i_type, inputs,
		partials, libraries,
		verbose=True,
		filepath=str,
	):
	"""
	# Create the factor by concatenating the files. Only used in cases
	# where the order of concatentation is already managed or irrelevant.

	# Requires 'execute-redirect'.
	"""
	return ['cat'] + list(inputs)

def empty(context, mechanism, factor, output, inputs,
		language=None,
		format=None,
		verbose=True,
	):
	"""
	# Create the factor by executing a command without arguments.
	# Used to create constant outputs for reduction.
	"""
	return ['empty']

def initial_factor_defines(factor, factorpath):
	"""
	# Generate a set of defines that describe the factor being created.
	# Takes the full module path of the factor as a string.
	"""
	parts = factorpath.split('.')
	project = '.'.join(factor.project.segment.absolute)

	tail = factorpath[len(project)+1:].split('.')[1:]

	return [
		('FACTOR_SUBPATH', '.'.join(tail)),
		('FACTOR_PROJECT', project),
		('FACTOR_QNAME', factorpath),
		('FACTOR_BASENAME', parts[-1]),
		('FACTOR_PACKAGE', '.'.join(parts[:-1])),
	]

class Construction(libio.Context):
	"""
	# Construction process manager. Maintains the set of target modules to construct and
	# dispatches the work to be performed for completion in the appropriate order.

	# [ Engineering ]
	# Primarily, this class traverses the directed graph constructed by imports
	# performed by the target modules being built.
	"""

	def terminate(self, by=None):
		# Manages the dispatching of processes,
		# so termination is immediate.
		self.exit()

	def __init__(self,
			context,
			symbols,
			index,
			project,
			factor,
			factors,
			core_include,
			reconstruct=False,
			processors=4
		):
		self.reconstruct = reconstruct
		self.failures = 0
		self.exits = 0
		self.c_sequence = None

		self.c_factor = factor
		self.c_symbols = symbols
		self.c_index = index
		self.c_context = context
		self.c_project = project
		self.c_factors = factors

		self.tracking = collections.defaultdict(list) # module -> sequence of sets of tasks
		self.progress = collections.Counter()

		self.process_count = 0 # Track available subprocess slots.
		self.process_limit = processors
		self.command_queue = collections.deque()

		self.continued = False
		self.activity = set()
		self.include_factor = core_include

		super().__init__()

	def actuate(self):
		if self.reconstruct:
			if self.reconstruct > 1:
				self._filter = functools.partial(updated, never=True, cascade=True)
			else:
				self._filter = functools.partial(updated, never=True, cascade=False)
		else:
			self._filter = functools.partial(updated)

		descent = functools.partial(requirements, self.c_index, self.c_symbols)

		# Manages the dependency order.
		self.c_sequence = sequence(descent, self.c_factors)

		initial = next(self.c_sequence) # generator init
		assert initial is None

		self.finish(())
		self.drain_process_queue()

		return super().actuate()

	def finish(self, factors):
		"""
		# Called when a set of factors have been completed.
		"""
		try:
			for x in factors:
				del self.progress[x]
				del self.tracking[x]

			work, reqs, deps = self.c_sequence.send(factors) # raises StopIteration
			for x in work:
				self.collect(x, reqs, deps.get(x, ()))
		except StopIteration:
			self.terminate()

	def collect(self, factor, requirements, dependents=()):
		"""
		# Collect the parameters and work to be done for processing the &factor.

		# [ Parameters ]
		# /factor/
			# The &Target being built.
		# /requirements/
			# The set of factors referred to by &factor. Often, the
			# dependencies that need to be built in order to build the factor.
		# /dependents/
			# The set of factors that refer to &factor.
		"""
		tracks = self.tracking[factor]

		if isinstance(factor, SystemFactor):
			# SystemFactors require no processing.
			self.finish([factor])
			return

		ctx = self.c_context
		reqs = requirements.get(factor, ())
		intention = ctx.intention
		f_name = factor.absolute_path_string

		common_src_params = initial_factor_defines(factor, f_name)
		selection = ctx.select(factor.domain)
		if selection is not None:
			variants, mech = selection
		else:
			# No mechanism found.
			sys.stderr.write("*! WARNING: no mechanism set for %r factors\n"%(factor.domain))
			return

		variants['name'] = factor.name
		variant_set = factor.link(variants, ctx, mech, reqs, dependents)

		# Subfactor of c_factor (selected path)
		subfactor = factor.absolute in self.c_factor
		xfilter = functools.partial(self._filter, subfactor=subfactor)
		envpath = factor.project.environment

		for src_params, (vl, key, locations) in variant_set:
			v = dict(vl)

			# The context parameters for rendering FPI.
			b_src_params = [
				('F_SYSTEM', v.get('system', 'void')),
				('F_INTENTION', intention),
				('F_FACTOR_DOMAIN', factor.domain),
				('F_FACTOR_TYPE', factor.type),
			] + src_params + common_src_params

			if not mech.integrates():
				# For mechanisms that do not specify reductions,
				# the transformed set is the factor.
				# XXX: Incomplete; check if specific output is absent.
				locations['output'] = locations['integral']

			build = Build((
				ctx, mech, factor, reqs, dependents,
				v, locations, b_src_params, envpath
			))
			xf = list(mech.transform(build, filtered=xfilter))

			# If any commands or calls are made by the transformation,
			# rebuild the target.
			for x in xf:
				if x[0] not in ('directory', 'link'):
					f = rebuild
					break
			else:
				# Otherwise, update if out dated.
				f = xfilter

			# Collect the exact mechanisms used for reference by integration.
			xfmechs = {}
			for src in build.factor.sources():
				langname = ctx.language(src.extension)
				xfmech = build.mechanism.adaption(build, langname, src, phase='transformations')
				if langname not in xfmechs:
					xfmechs[langname] = xfmech

			fi = list(mech.integrate(xfmechs, build, filtered=f))
			if xf or fi:
				pf = list(mech.prepare(build))
			else:
				pf = ()

			tracks.extend((pf, xf, fi))

		if tracks:
			self.progress[factor] = -1
			self.dispatch(factor)
		else:
			self.activity.add(factor)

			if self.continued is False:
				# Consolidate loading of the next set of processors.
				self.continued = True
				self.ctx_enqueue_task(self.continuation)

	def process_execute(self, instruction, f_target_path=(lambda x: str(x))):
		factor, ins = instruction
		typ, cmd, log, io, *tail = ins
		target = io[1]

		stdout = stdin = os.devnull

		if typ == 'execute-stdio':
			stdout = str(io[1])
			stdin = str(io[0][0]) # Catenate for integrations?
			iostr = ' <' + str(stdin) + ' >' + stdout
		elif typ == 'execute-redirection':
			stdout = str(io[1])
			iostr = ' >' + stdout
		else:
			iostr = ''

		assert typ in ('execute', 'execute-redirection', 'execute-stdio')

		strcmd = tuple(map(str, cmd))

		pid = None
		with log.open('wb') as f:
			f.write(b'[Command]\n')
			f.write(' '.join(strcmd).encode('utf-8'))
			f.write(b'\n\n[Standard Error]\n')

			ki = libsys.KInvocation(str(cmd[0]), strcmd, environ=dict(os.environ))
			with open(stdin, 'rb') as ci, open(stdout, 'wb') as co:
				pid = ki(fdmap=((ci.fileno(), 0), (co.fileno(), 1), (f.fileno(), 2)))
				sp = libio.Subprocess(pid)

		fpath = factor.absolute_path_string
		pidstr = str(pid)
		formatted = {str(target): f_target_path(target)}
		printed_command = tuple(formatted.get(x, x) for x in map(str, cmd))
		command_string = ' '.join(printed_command) + iostr
		sys.stderr.write("-> [%s:%d] %s\n" %(fpath, pid, command_string))

		self.sector.dispatch(sp)
		sp.atexit(functools.partial(
			self.process_exit,
			start=libtime.now(),
			descriptor=(typ, cmd, log),
			factor=factor,
			message=command_string,
		))

	def process_exit(self, processor,
			start=None, factor=None, descriptor=None,
			message=None,
			_color='\x1b[38;5;1m',
			_pid='\x1b[38;5;2m',
			_normal='\x1b[0m'
		):
		assert factor is not None
		assert descriptor is not None

		self.progress[factor] += 1
		self.process_count -= 1
		self.activity.add(factor)

		typ, cmd, log = descriptor
		pid, status = processor.only
		exit_method, exit_code, core_produced = status

		self.exits += 1
		if exit_code != 0:
			self.failures += 1

			if message is not None:
				duration = repr(start.measure(libtime.now()))
				prefix = "%s: %d -> %s in %s\n\t" %(
					_color + factor.absolute_path_string + _normal,
					pid,
					_color + str(exit_code) + _normal,
					str(duration)
				)
				print(prefix+message)

		l = ''
		l += ('\n[Profile]\n')
		l += ('/factor/\n\t%s\n' %(factor,))

		if log.points[-1] != 'reduction':
			l += ('/subject/\n\t%s\n' %('/'.join(log.points),))
		else:
			l += ('/subject/\n\treduction\n')

		l += ('/pid/\n\t%d\n' %(pid,))
		l += ('/status/\n\t%s\n' %(str(status),))
		l += ('/start/\n\t%s\n' %(start.select('iso'),))
		l += ('/stop/\n\t%s\n' %(libtime.now().select('iso'),))

		log.store(l.encode('utf-8'), mode='ba')

		if self.continued is False:
			# Consolidate loading of the next set of processors.
			self.continued = True
			self.ctx_enqueue_task(self.continuation)

	def drain_process_queue(self):
		"""
		# After process slots have been cleared by &process_exit,
		# &continuation is called and performs this method to execute
		# system processes enqueued in &command_queue.
		"""
		# Process slots may have been cleared, run more if possible.
		nitems = len(self.command_queue)
		if nitems > 0:
			# Identify number of processes to spawn.
			# &process_exit decrements the process_count, so the available
			# logical slots are normally the selected count. Minimize
			# on the number of items in the &command_queue.
			pcount = min(self.process_limit - self.process_count, nitems)
			for x in range(pcount):
				cmd = self.command_queue.popleft()
				self.process_execute(cmd)
				self.process_count += 1

	def continuation(self):
		"""
		# Process exits occurred that may trigger an addition to the working set of tasks.
		# Usually called indirectly by &process_exit, this manages the collection
		# of further work identified by the sequenced dependency tree managed by &sequence.
		"""
		# Reset continuation
		self.continued = False
		factors = list(self.activity)
		self.activity.clear()

		completions = set()

		for x in factors:
			tracking = self.tracking[x]
			if not tracking:
				# Empty tracking sets.
				completions.add(x)
				continue

			if self.progress[x] >= len(tracking[0]):
				# Pop action set.
				del tracking[0]
				self.progress[x] = -1

				if not tracking:
					# Complete.
					completions.add(x)
				else:
					# dispatch new set of instructions.
					self.dispatch(x)
			else:
				# Nothing to be done; likely waiting on more
				# process exits in order to complete the task set.
				pass

		if completions:
			self.finish(completions)

		self.drain_process_queue()

	def dispatch(self, factor):
		"""
		# Process the collected work for the factor.
		"""
		assert self.progress[factor] == -1
		self.progress[factor] = 0

		for x in self.tracking[factor][0]:
			typ, cmd, logfile, *tail = x

			if typ in ('execute', 'execute-redirection', 'execute-stdio'):
				self.command_queue.append((factor, x))
			elif typ == 'directory':
				tail[0][1].init('directory')

				self.progress[factor] += 1
			elif typ == 'link':
				src, dst = tail[0]
				dst.link(src)

				self.progress[factor] += 1
			elif typ == 'call':
				try:
					cmd[0](*cmd[1:])
					if logfile.exists():
						logfile.void()
				except BaseException as err:
					self.failures += 1
					pi_call = cmd[0]
					pi_call_id = '.'.join((pi_call.__module__, pi_call.__name__))
					print(factor.absolute_path_string, 'call (%s) raised' % (pi_call_id,), err.__class__.__name__, str(err))

					from traceback import format_exception
					out = format_exception(err.__class__, err, err.__traceback__)
					logfile.store('[Exception]\n#!/traceback\n\t', 'w')
					logfile.store('\t'.join(out).encode('utf-8'), 'ba')

				self.progress[factor] += 1
			else:
				print('unknown instruction', x)

		if self.progress[factor] >= len(self.tracking[factor][0]):
			self.activity.add(factor)

			if self.continued is False:
				self.continued = True
				self.ctx_enqueue_task(self.continuation)
