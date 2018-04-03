"""
# Construction Context implementation in Python.

# [ Properties ]

# /library_extensions
	# Used by &library_filename to select the appropriate extension
	# for (factor/type)`system.library` and (factor/type)`system.extension` factors.

# /intentions
	# Construction intentions known to the implementation
	# associated with a sentence describing it.
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

from . import include

from ..computation import library as libc
from ..chronometry import library as libtime
from ..routes import library as libroutes
from ..io import library as libio
from ..system import library as libsys
from ..system import libfactor
from ..filesystem import library as libfs

from ..xml import library as libxml
from ..xml import lxml

Import = libroutes.Import
File = libroutes.File

fpi_addressing = libfs.Hash('fnv1a_32', depth=1, length=2)

xml_namespaces = {
	'lc': 'http://fault.io/xml/dev/fpi',
	'd': 'http://fault.io/xml/data',
	'ctx': 'http://fault.io/xml/dev/ctx',
}

intentions = {
	'optimal': "Subjective performance selection",
	'debug': "Reduced optimizations and defines for emitting debugging information",

	'test': "Debugging intention with support for injections for comprehensive testing",
	'metrics': "Test intention with profiling and coverage collection enabled",

	'profiling': "Raw profiling build for custom collections",
	'coverage': "Raw coverage build for custom collections",

	'delineation': "Context used to extract fragments from source files",
}

intention_flags = {
	'optimal': '-O',
	'debug': '-g',

	'test': '-t',
	'metrics': '-M',

	'profiling': '-P',
	'coverage': '-C',

	'delineation': '-i',
}

library_extensions = {
	'msw': 'dll',
	'win32': 'dll',
	'darwin': 'dylib',
	'unix': 'so',
}

def library_filename(platform, name):
	"""
	# Construct a dynamic library filename for the given platform.
	"""
	return 'lib' + name.lstrip('lib') + '.' + library_extensions.get(platform, 'so')

def strip_library_name(filename):
	prefix, *suffix = filename.split('.', 1)

	if prefix.startswith('lib'):
		return prefix[3:]

	return prefix

def python_context(implementation, version_info, abiflags, platform):
	"""
	# Construct the triplet representing the Python context for the platform.
	# Used to define the construction context for Python extension modules.
	"""
	pyversion = ''.join(map(str, version_info[:2]))
	return '-'.join((implementation, pyversion + abiflags, platform))

runtime_bytecode_triplet = python_context(
	sys.implementation.name, sys.version_info, '', 'bytecode'
)

def update_named_mechanism(route:libroutes.File, name:str, data):
	"""
	# Given a route to a mechanism file in a construction context,
	# overwrite the file's mechanism entry with the given &data.

	# [ Parameters ]
	# /route
		# The route to the file that is to be modified.
	# /name
		# The xml:id used to identify the mechanism layer.
	# /data
		# The dictionary to set as the mechanism's content.
	"""
	from fault.xml.lxml import Query

	raw = lxml.etree.parse(str(route))
	q = Query(raw, xml_namespaces)

	S = libxml.Serialization()
	D = S.switch('data:')
	fragment = b''.join(S.element('mechanism',
		libxml.Data.serialize(D, data),
		('xml:id', name),
		('xmlns', 'http://fault.io/xml/dev/fpi'),
		('xmlns:data', 'http://fault.io/xml/data'),
	))
	fdoc = lxml.etree.XML(fragment).xpath('/*')[0]

	current_mechanism = q.first('/lc:context/lc:mechanism[@xml:id=%r]' % (name,))
	if current_mechanism is None:
		q.append('/lc:context', fdoc)
	else:
		current_mechanism.replace('.', fdoc)

	return route.store(lxml.etree.tostring(q.element))

def load_named_mechanism(route:libroutes.File, name:str):
	"""
	# Given a route to a mechanism file in a construction context,
	# load the file's mechanism entry.

	# [ Parameters ]
	# /route
		# The route to the file that is to be modified.
	# /name
		# The xml:id used to identify the mechanism layer.
	"""
	raw = lxml.etree.parse(str(route))
	data = raw.xpath(
		"/lc:context/lc:mechanism[@xml:id=%r]/d:*" %(name,),
		namespaces=xml_namespaces)

	data = list(data)
	if data:
		return libxml.Data.structure(data[0])

	return {}

def rebuild(outputs, inputs):
	"""
	# Unconditionally report the &outputs as outdated.
	"""
	return False

def updated(outputs, inputs, requirement=None):
	"""
	# Return whether or not the &outputs are up-to-date.

	# &False returns means that the target should be reconstructed,
	# and &True means that the file is up-to-date and needs no processing.
	"""
	olm = None
	for output in outputs:
		if not output.exists():
			# No such object, not updated.
			return False
		lm = output.last_modified()
		olm = min(lm, olm or lm)

	if requirement is not None and olm < requirement:
		# Age requirement not meant, rebuild.
		return False

	for x in inputs:
		if not x.exists() or x.last_modified() > olm:
			# rebuild if any output is older than any source.
			return False

	# object has already been updated.
	return True

# Resolve cache_from_source.
try:
	import importlib.util
	cache_from_source = importlib.util.cache_from_source
except (ImportError, AttributeError):
	try:
		import imp
		cache_from_source = imp.cache_from_source
		del imp
	except (ImportError, AttributeError):
		# Make a guess preferring the cache directory.
		def cache_from_source(filepath):
			return os.path.join(
				os.path.dirname(filepath),
				'__pycache__',
				os.path.basename(filepath) + 'c'
			)
finally:
	pass

def update_bytecode_cache(src, induct, condition,
		cache_from_source=cache_from_source,
		mkr=libroutes.File.from_path
	) -> typing.Tuple[bool, str]:
	"""
	# Determine whether to update the cached Python bytecode file associated
	# with &src.

	# [ Parameters ]
	# /src
		# A Python source &File properly positioned in its package directory.
		# &importlib.util.cache_from_source will be called to find its
		# final destination.
	# /induct
		# Compiled bytecode &File to install.

	# [ Returns ]
	# /&bool
		# Whether the file was updated or not.
	# /&str
		# The string path to the cache file location
		# that should be overwritten.

		# When &1 is &False, this will be a message describing
		# why it should not be updated.
	"""

	fp = str(src)
	if not src.exists() or not fp.endswith('.py'):
		return (False, 'source does not exist or does not end with ".py"')

	cache_file = mkr(cache_from_source(fp, optimization=None))

	if condition((cache_file,), (induct,)):
		return (False, "update condition was not present")

	return (True, cache_file)

def references(factors):
	container = collections.defaultdict(set)
	for f in factors:
		container[f.pair].add(f)
	return container

class SystemFactor(object):
	"""
	# Factor structure used to provide access to include and library directories.
	# Instances are normally stored in &Build.references which is populated by
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

	def __init__(self, **kw):
		for k in ('sources', 'integral'):
			v = kw.pop(k, None)
			kw['_'+k] = v

		self.__dict__.update(kw)

	def sources(self):
		return self.__dict__['_sources']

	def integral(self):
		return self.__dict__['_integral']
iFactor = SystemFactor

class Factor(object):
	"""
	# A Factor of a development environment; similar to "targets" in IDEs.
	# &Factor instances are specific to the module-local Construction Context
	# implementation.

	# Initialized with the primary dependencies of most operations to avoid
	# redundancy and in order to allow simulated factors to be managed without
	# modifying or cleaning up &sys.modules.

	# [ Properties ]
	# /local_variants
		# Explicitly designated variants.
	"""

	default_source_directory = 'src'
	default_cache_name = '__pycache__'
	default_fpi_name = '.fpi'

	def __repr__(self):
		return "{0.__class__.__name__}({1}, {2}, {3})".format(
			self,
			self.route,
			self.module,
			self.parameters
		)

	def __hash__(self):
		p = list(self.parameters or ())
		p.sort()
		return hash((self.module, tuple(p)))

	def __eq__(self, ob):
		if not isinstance(ob, Factor):
			return False
		return ob.module == self.module and ob.parameters == self.parameters

	@staticmethod
	@functools.lru_cache(32)
	def _directory_cache(route):
		parent = route.container
		if (parent.context, parent.points) != (None, ()):
			return Factor._directory_cache(route.container) / route.identifier
		else:
			return route

	def __init__(self,
			route:Import,
			module:types.ModuleType, module_file:File,
			parameters:typing.Mapping=None,
		):
		"""
		# Either &route or &module can be &None, but not both. The system's
		# &importlib will be used to resolve a module from the &route in its
		# absence, and the module's (python:attribute)`__name__` field will
		# be used to construct the &Import route given &route's absence.
		"""
		self.local_variants = {}
		self.key = None

		if route is None:
			route = Import.from_fullname(module.__name__)
		elif module is None:
			module = importlib.import_module(str(route))

		self.route = route
		self.module = module

		if module_file is None:
			mfp = getattr(module, '__file__', None)
			if mfp is not None:
				# Potentially, this could be a purposeful lie.
				module_file = File.from_absolute(mfp)
			else:
				# Get it from Python's loader.
				module_file = route.file()

		pkgdir = self._directory_cache(module_file.container)
		self.package_directory = pkgdir
		self.module_file = pkgdir / module_file.identifier

		if parameters is None:
			# Collect from module if available.
			parameters = getattr(module, 'parameters', None)
			self.parameters = parameters

	@classmethod
	def from_fullname(Class, fullname):
		"""
		# Create from a module's fullname that is available on &sys.path.
		"""
		return Class(Import.from_fullname(fullname), None, None)

	@classmethod
	def from_module(Class, module):
		"""
		# Create from a &types.ModuleType. This constructor should be used in
		# cases where a Factor is being simulated and is not addressable in
		# Python's module path.
		"""
		if hasattr(module, '__factor__'):
			return module.__factor__
		return Class(None, module, None)

	@property
	@functools.lru_cache(32)
	def fullname(self):
		return self.route.fullname

	def __str__(self):
		struct = "({0.domain}.{0.type}) {0.fullname}[{0.module_file.fullpath}]"
		return struct.format(self, scheme=self.type[:3])

	@property
	def name(self):
		return self.route.identifier

	@property
	def domain(self):
		try:
			return self.module.__factor_domain__
		except AttributeError:
			# python.library
			return 'python'

	@property
	def type(self):
		try:
			return self.module.__factor_type__
		except AttributeError:
			# python.library
			return 'library'

	@property
	def reflective(self):
		try:
			return self.module.reflective
		except AttributeError:
			return False

	@property
	def pair(self):
		return (self.domain, self.type)

	@property
	def latest_modification(self):
		return scan_modification_times(self.package_directory)

	@property
	def source_directory(self):
		"""
		# Get the factor's source directory.
		"""
		srcdir = self.package_directory / self.default_source_directory
		if not srcdir.exists():
			return self.package_directory
		return srcdir

	def sources(self):
		"""
		# An iterable producing the source files of the Factor.
		"""
		# Full set of regular files in the sources location.
		fs = getattr(self.module, '__factor_sources__', None)
		if fs is not None:
			return fs
		else:
			srcdir = self.source_directory
			if srcdir.exists():
				return [
					srcdir.__class__(srcdir, (srcdir >> x)[1])
					for x in srcdir.tree()[1]
				]

	@property
	def cache_directory(self) -> File:
		"""
		# Python cache directory to use for the factor.
		"""
		return self.package_directory / self.default_cache_name

	@property
	def fpi_root(self) -> File:
		"""
		# Factor Processing Instruction root work directory for the given Factor, &self.
		"""
		return self.cache_directory / self.default_fpi_name

	@staticmethod
	def fpi_work_key(variants):
		"""
		# Calculate the key from the sorted list.

		# Sort function is of minor importance, there is no warranty
		# of consistent accessibility across platform.
		"""
		return ';'.join('='.join((k,v)) for k,v in variants).encode('utf-8')

	def fpi_initialize(self, *variant_sets, **variants):
		"""
		# Update and return the dictionary key used to access the processed factor.
		"""
		vl = list(itertools.chain.from_iterable(v.items() for v in variant_sets))
		vl.extend(self.local_variants.items())
		vl.extend(variants.items())
		vl = list(dict(vl).items())
		vl.sort()

		key = self.fpi_work_key(vl)
		wd = self.fpi_set.route(key, filename=str)

		return vl, key, {
			'work': wd, # normally, __pycache__ subdirectory.
			# Processed Source Directory; becomes ftr if no reduce.
			'output': wd / 'psd',
			'log': wd / 'log',
			'integral': wd / 'int',
			'libraries': wd / 'lib',
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

	def integral(self, key=None, slot='factor'):
		"""
		# Get the appropriate reduction for the Factor based on the
		# configured &key. If no key has been configured, the returned
		# route will be to the inducted factor.
		"""

		if getattr(self.module, 'reflection', False):
			return self.source_directory

		if key is not None and self.fpi_work_exists(key):
			r = self.fpi_set.route(key) / 'int'
			if not r.exists():
				r = libfactor.inducted(self.route, slot=slot)
		else:
			r = libfactor.inducted(self.route, slot=slot)

		if not r.exists():
			raise RuntimeError("factor reduction does not exist", r, self)

		return r

	def dependencies(factor):
		"""
		# Return the set of dependencies that the given factor has.
		"""

		is_composite = libfactor.composite
		ModuleType = types.ModuleType

		refs = set(x for x in factor.module.__dict__.values() if isinstance(x, ModuleType))
		for v in refs:
			if not hasattr(v, '__factor_type__'):
				# Factor, but no type means that
				# it has no transformation to perform.
				continue
			if not hasattr(v, '__factor_domain__'):
				continue

			yield Factor(None, v, None)

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

	def link(self, variants, context, mechanism, refs, dependents):
		"""
		# Generate the variants, source parameters, and locations used
		# to perform a build.

		# [ Parameters ]
		# /context
			# &Context instance providing the required mechanisms.
		# /mechanism
			# &Mechanism selected for production of the Factor Processing Instructions.
		# /refs
			# The dependencies, composite factors, specified by imports.
		# /dependents
			# The list of Factors depending on this target.
		"""

		for fmt in self.formats(mechanism, dependents):
			vars = dict(variants)
			vars['format'] = fmt

			yield [], self.fpi_initialize(vars, format=fmt)

def scan_modification_times(factor, aggregate=max):
	"""
	# Scan the factor's sources for the latest modification time.
	"""
	dirs, files = libfactor.sources(factor).tree()
	del dirs

	glm = File.get_last_modified
	return aggregate(x for x in map(glm, files))

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

	# /descriptor
		# The data structure referring to the interface used
		# to construct commands for the selected mechanism.
	# /cache
		# Mapping of resolved adapters. Used internally for handling
		# adapter inheritance.
	"""

	def __init__(self, descriptor):
		self.cache = {}
		self.descriptor = descriptor

	@property
	def integrations(self):
		return self.descriptor['integrations']

	def integrates(self):
		ints = self.descriptor.get('integrations')
		if ints:
			return True
		else:
			return False

	@property
	def transformations(self):
		return self.descriptor['transformations']

	def suffix(self, factor):
		"""
		# Return the suffix that the given factor should use for its integral.
		"""
		tfe = self.descriptor['target-file-extensions']
		return (
			tfe.get(factor.type) or \
			tfe.get(None) or '.i'
		)

	def prepare(self, build):
		"""
		# Generate any requisite filesystem initializations.
		"""

		loc = build.locations
		f = build.factor
		ftr = loc['integral']
		rr = ftr / (f.name + self.suffix(f))

		yield ('directory', None, None, (None, ftr))
		if not f.reflective:
			yield ('link', None, None, (rr, ftr / 'pf.lnk'))

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
		while 'inherit' in lmech:
			basemech = lmech['inherit']
			layers.append(aset[basemech]) # mechanism inheritance
			lmech = aset[basemech]
		layers.reverse()

		cmech = {}
		for x in layers:
			merge(cmech, x)
		cmech.pop('inherit', None)

		# cache merged mechanism
		acache[(phase, domain)] = cmech

		return cmech

	def transform(self, build, filtered=rebuild):
		"""
		# Transform the sources using the mechanisms defined in &context.
		"""
		global languages, include

		f = build.factor
		fdomain = f.domain
		loc = build.locations
		logs = loc['log']
		ctxname = build.context.name
		fmt = build.variants['format']

		mechanism = build.mechanism.descriptor
		ignores = mechanism.get('ignore-extensions', ())

		commands = []
		for src in f.sources():
			fnx = src.extension
			if ctxname != 'delineation' and fnx in ignores or src.identifier.startswith('.'):
				# Ignore header files and dot-files for non-delineation contexts.
				continue
			obj = File(loc['output'], src.points)

			if filtered((obj,), (src,)):
				continue

			logfile = File(loc['log'], src.points)

			src_type = languages.get(src.extension)
			out_format = mechanism['formats'][f.type]

			adapter = self.adaption(build, src_type, src, phase='transformations')
			xf = context_interface(adapter['interface'])

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
		if 'integrations' not in mechanism or f.reflective:
			return

		mechp = mechanism
		preferred_suffix = self.suffix(f)

		ftr = loc['integral']
		rr = ftr / (f.name + preferred_suffix)

		# Discover the known sources in order to identify which objects should be selected.
		objdir = loc['output']
		sources = set([
			x.points for x in f.sources()
			if x.extension not in mechp.get('ignore-extensions', ())
		])
		# TODO: Filter objects whose suffix isn't in &sources or in output/.ext/*
		objects = [
			objdir.__class__(objdir, x) for x in sources
		]

		partials = [x for x in build.references[(f.domain, 'partial')]]
		if filtered((rr,), objects):
			return

		adapter = self.adaption(build, f.type, objects, phase='integrations')

		# Mechanisms with a configured root means that the
		# transformed objects will be referenced by the root file.
		root = adapter.get('root')
		if root is not None:
			objects = [objdir / root]

		# Libraries and partials of the same domain are significant.
		libraries = [x for x in build.references[(f.domain, 'library')]]

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
	references = property(operator.itemgetter(3))
	dependents = property(operator.itemgetter(4))
	variants = property(operator.itemgetter(5))
	locations = property(operator.itemgetter(6))
	parameters = property(operator.itemgetter(7))

	def pl_specification(self, language):
		module = self.factor.module
		return module.__dict__.get('pl', {}).get(language, (None, ()))

class Parameters(object):
	"""
	# Stored Parameters interface for retrieving and updating parameters.

	# [ Properties ]
	# /route
		# Route to the directory containing the context's parameters.
	"""

	def __init__(self, routes):
		self.routes = routes

	@staticmethod
	@functools.lru_cache(16)
	def load_reference_xml(route:File):
		"""
		# Load the reference parameter required by a factor.
		"""

		with route.open('r') as f:
			xml = lxml.etree.parse(f)
		params = {}

		xml.xinclude()
		d = xml.xpath('/ctx:reference/d:dictionary', namespaces=xml_namespaces)

		# Merge context data in the order they appear.
		for x in d:
			# Attributes on the context element define the variant.
			data = libxml.Data.structure(x)
			merge(params, data)

		authority = xml.xpath('/ctx:reference/@authority', namespaces=xml_namespaces) or (None,)
		authority = authority[0]

		name = route.identifier.split('.', 1)[0]

		return (name, authority, params)

	def factors(self, *parameter) -> typing.Sequence[SystemFactor]:
		"""
		# Return the factors of the given reference parameter.
		"""

		return self.load(*parameter)[-1].get('factors', {})

	def load(self, *parameter):
		"""
		# Return the factors of the given reference parameter.
		"""

		*suffix, name = parameter
		name = name + '.xml'

		for path in self.routes:
			f = path.extend(suffix)
			f = f / name
			if f.exists():
				break
		else:
			return name, None, {}

		return self.load_reference_xml(f)

	def tree(self, directory):
		"""
		# Construct and return a mapping of parameter paths to their
		# correspeonding data. Used to load sets of parameters.

		# The keys in the returned mapping do not include the named &directory.
		"""
		seq = directory.split('/')
		out = {}
		product = []
		p_prefix_len = len(directory) + 1

		for path in self.routes:
			r = path.extend(seq)
			files = r.tree()[1]
			prefix = len(str(path)) + 1
			files = [str(f)[prefix:-4] for f in files]

			for f in files:
				if f in out:
					continue
				out[f[p_prefix_len:]] = self.load(f)[-1]

		return out

	@staticmethod
	def serialize_parameters(xml:libxml.Serialization, authority:str, data):
		"""
		# Construct an iterator producing the serialized form of a reference
		# parameter for storage in a construction context.
		"""
		sdata = libxml.Data.serialize(xml, data)

		x = xml.root("ctx:reference", sdata,
			('xmlns:ctx', 'http://fault.io/xml/dev/ctx'),
			('authority', authority),
			namespace=libxml.Data.namespace
		)

		return x

	@classmethod
	def store(Class, route, authority, data):
		xml = libxml.Serialization()
		x = Class.serialize_parameters(xml, authority, data,)
		route.store(b''.join(x))

class Context(object):
	"""
	# A sequence of mechanism sets, Construction Context, that
	# can be used to supply a given build with tools for factor
	# processing.

	# [ Engineering ]
	# This class is actually a Context implementation and should be relocated
	# to make room for a version that interacts with an arbitrary context
	# for use in scripts that perform builds. Direct use is not actually
	# intended as it's used to house the mechanisms.
	"""

	def __init__(self, sequence, parameters):
		self.sequence = sequence or ()
		self.parameters = parameters

	def f_target(self, factor):
		"""
		# Return the &libroutes.File route to the factor's target file built
		# using this Construction Context.
		"""
		vars, mech = self.select(factor.domain)
		#refs = self.references(factor.dependencies())
		refs = []
		(sp, (vl, key, loc)), = factor.link(dict(vars), self, mech, refs, ())
		primary = loc['integral'] / 'pf.lnk'
		return primary

	@property
	@functools.lru_cache(8)
	def name(self):
		"""
		# The context name identifying the target architectures.
		"""
		return self.parameters.load('context')[-1]['name']

	@functools.lru_cache(8)
	def intention(self, fdomain):
		"""
		# The intention of the Context for the given factor domain.

		# While usually consistent across the mechanism sets, there are
		# cases where an implementation chooses to reduce the intentions
		# where it is known that the builds are consistent. Python bytecode
		# being the notable case where (intention)`debug` is consistent
		# with (intention)`test` and (intention)`measure`.

		# Presumes optimal if the mechanism sets did not define a intention.
		# This is used for compensating cases where the generated mechanism
		# sets have consistent intentions for automated builds.
		"""
		return self.parameters.load('context')[-1]['intention']

	@functools.lru_cache(8)
	def select(self, fdomain):
		# Scan the data set for the domain instantiating a mechanism.
		for x in self.sequence:
			if fdomain in x:
				mechdata = x[fdomain]
				return x['variants'], Mechanism(mechdata)
		else:
			# Select the [trap] if available.
			for x in self.sequence:
				if '[trap]' in x:
					return x['variants'], Mechanism(x['[trap]'])

	def __bool__(self):
		"""
		# Whether the Context has any mechanisms.
		"""
		return bool(self.sequence)

	@staticmethod
	def load_xml(route:File):
		"""
		# Load the XML context designated by the &route.
		"""

		with route.open('r') as f:
			xml = lxml.etree.parse(f)

		variants = {}
		context = {}

		xml.xinclude()
		context_mechanisms = xml.xpath('/lc:context/lc:mechanism', namespaces=xml_namespaces)

		# Merge context data in the order they appear.
		for x in context_mechanisms:
			# Attributes on the context element define the variant.
			variants.update(x.attrib)

			for dictionary in x:
				data = libxml.Data.structure(dictionary)
				merge(context, data)

		if 'xml:id' in variants:
			del variants['xml:id']

		context['variants'] = variants
		return xml, context

	@classmethod
	def from_environment(Class, envvar='FPI_MECHANISMS', pev='FPI_PARAMETERS'):
		mech_refs = os.environ.get(envvar, '').split(os.pathsep)
		seq = []
		for mech in mech_refs:
			xml, ctx = Class.load_xml(File.from_absolute(mech))
			seq.append(ctx)

		param_paths = os.environ.get(pev, '').split(os.pathsep)
		param_paths = [libroutes.File.from_absolute(x) for x in param_paths if x]

		r = Class(seq, Parameters(param_paths))
		return r

	@classmethod
	def from_directory(Class, route):
		p = Parameters([route / 'parameters'])
		return Class([], p)

# Specifically for identifying files to be compiled and how.
extensions = {
	'txt': ('txt',),
	'c-header': ('h',),
	'c++-header': ('hpp', 'hxx',),
	'objective-c-header': ('hm',),

	'c': ('c',),
	'c++': ('c++', 'cpp', 'cxx',),
	'objective-c': ('m',),
	'objective-c++': ('mm',),

	'ada': ('ads', 'ada'),
	'assembly': ('asm',),
	'bitcode': ('bc',), # clang
	'haskell': ('hs', 'hsc'),
	'd': ('d',),
	'rust': ('rs',),

	'python': ('py',),
	'bytecode.python': ('pyo', 'pyc',),
	'pyrex.python': ('pyx',),

	'javascript': ('json', 'js'),
	'css': ('css',),
	'xml': ('xml', 'xsl', 'rdf', 'rng',),
	'html': ('html', 'htm'),
	'archive.system': ('a',),
	'library.system': ('dll', 'so', 'lib'),
	'jar.java': ('jar',),
	'wheel.python': ('whl',),
	'egg.python': ('egg',),

	'awk': ('awk',),
	'sed': ('sed',),
	'c-shell': ('csh',),
	'korn-shell': ('ksh',),
	'bourne-shell': ('sh',),

	'perl': ('pl',),
	'ruby': ('ruby',),
	'php': ('php',),
	'lisp': ('lisp',),
	'lua': ('lua',),
	'io': ('io',),
	'java': ('java',),
	'ocaml': ('ml',),
	'ada': ('ads', 'ada'),
}

languages = {}
for k, v in extensions.items():
	for y in v:
		languages[y] = k
del k, y, v

def simulate_composite(route):
	"""
	# Given a Python package route, fabricate a composite factor in order
	# to process Python module sources.

	# [ Returns ]

	# A pair consisting of the fabricated module and the next set of packages to process.
	"""
	pkgs, modules = route.subnodes()

	if not route.exists():
		raise ValueError(route) # module does not exist?

	modules.append(route)
	sources = [
		x.__class__(x.container, (x.identifier,))
		for x in [x.file() for x in modules if x.exists()]
		if x is not None and x.extension == 'py'
	]
	pkgfile = route.file()

	mod = types.ModuleType(str(route), "Simulated composite factor for bytecode compilation")
	mod.__factor_domain__ = 'bytecode.python'
	mod.__factor_type__ = 'library' # Truthfully, a [python] Package Module.
	mod.__factor_sources__ = sources # Modules in the package.
	mod.__factor_context__ = runtime_bytecode_triplet
	mod.__file__ = str(pkgfile)

	return mod, pkgs

def gather_simulations(packages:typing.Sequence[Import]):
	# Get the simulations for the bytecode files.
	next_set = packages

	while next_set:
		current_set = next_set
		next_set = []

		for pkg in current_set:
			mod, adds = simulate_composite(pkg)
			f = Factor(Import.from_fullname(mod.__name__), mod, None)
			next_set.extend(adds)

			yield f

# The extension suffix to use for *this* Python installation.
python_extension_suffix = importlib.machinery.EXTENSION_SUFFIXES[0]

def link_extension(route, factor):
	"""
	# Link an inducted Python extension module so that the constructed binary
	# can be used by (python:statement)`import`.

	# Used by &.bin.induct after copying the target's factor to the &libfactor.

	# [ Parameters ]
	# /route
		# The &Import selecting the composite factor to induct.
	"""

	# system.extension being built for this Python
	# construct links to optimal.
	# ece's use a special context derived from the Python install
	# usually consistent with the triplet of the first ext suffix.
	src = os.readlink(str(factor / 'pf.lnk'))
	src = factor / src

	# peel until it's outside the first extensions directory.
	pkg = route
	while pkg.identifier != 'extensions':
		pkg = pkg.container
	names = route.absolute[len(pkg.absolute):]
	pkg = pkg.container

	link_target = pkg.file().container.extend(names)
	final = link_target.suffix(python_extension_suffix)

	final.link(src)

	return (final, src)

def traverse(working, tree, inverse, factor):
	"""
	# Invert the directed graph of dependencies from the target modules.

	# System factor modules import their dependencies into their global
	# dictionary forming a directed graph. The imported factor modules are
	# identified as dependencies that need to be constructed in order
	# to process the subject module. The inverted graph is constructed to manage
	# completion signalling for processing purposes.
	"""

	deps = set(factor.dependencies())

	if not deps:
		# No dependencies, add to working set and return.
		working.add(factor)
		return
	elif factor in tree:
		# It's already been traversed in a previous run.
		return

	# dependencies present, assign them inside the tree.
	tree[factor] = deps

	for x in deps:
		# Note the factor as depending on &x and build
		# its tree.
		inverse[x].add(factor)
		traverse(working, tree, inverse, x)

def sequence(factors):
	"""
	# Generator maintaining the state of sequencing a traversed factor depedency
	# graph. This generator emits factors as they are ready to be processed and receives
	# factors that have completed processing.

	# When a set of dependencies has been processed, they should be sent to the generator
	# as a collection; the generator identifies whether another set of modules can be
	# processed based on the completed set.

	# Completion is an abstract notion, &sequence has no requirements on the semantics of
	# completion and its effects; it merely communicates what can now be processed based
	# completion state.
	"""

	refs = dict()
	tree = dict() # dependency tree; F -> {DF1, DF2, ..., DFN}
	inverse = collections.defaultdict(set)
	working = set()
	for factor in factors:
		traverse(working, tree, inverse, factor)

	new = working
	# Copy tree.
	for x, y in tree.items():
		cs = refs[x] = collections.defaultdict(set)
		for f in y:
			cs[f.pair].add(f)

	yield None

	while working:
		# Build categorized dependency set for use by mechanisms.
		for x in new:
			if x not in refs:
				refs[x] = collections.defaultdict(set)

		completion = (yield tuple(new), refs, {x: tuple(inverse[x]) for x in new if inverse[x]})
		for x in new:
			refs.pop(x, None)
		new = set() # &completion triggers new additions to &working

		for factor in (completion or ()):
			# completed.
			working.discard(factor)

			for deps in inverse[factor]:
				tree[deps].discard(factor)
				if not tree[deps]:
					# Add to both; new is the set reported to caller,
					# and working tracks when the graph has been fully sequenced.
					new.add(deps)
					working.add(deps)

					del tree[deps]

def identity(module):
	"""
	# Discover the base identity of the target.

	# Primarily, used to identify the proper basename of a library.
	# The (python/attribute)`name` attribute on a target module provides an explicit
	# override. If the `name` is not present, then the first `'lib'` prefix
	# is removed from the module's name if any. The result is returned as the identity.
	# The removal of the `'lib'` prefix only occurs when the target factor is a
	# `'system.library'`.
	"""
	na = getattr(module, 'name', None)
	if na is not None:
		# explicit name attribute providing an override.
		return na

	idx = module.__name__.rfind('.')
	basename = module.__name__[idx+1:]
	if module.__factor_type__ == 'library':
		if basename.startswith('lib'):
			# strip the leading lib from module identifier.
			# 'libNAME' returns 'NAME'
			return basename[3:]

	return basename

def disabled(*args, **kw):
	"""
	# A transformation that can be assigned to a subject's mechanism
	# in order to describe it as being disabled.
	"""
	return ()

def transparent(build, adapter, o_type, output, i_type, inputs,
		verbose=True,
	):
	"""
	# Create links from the input to the output; used for zero transformations.
	"""

	input, = inputs # Rely on exception from unpacking; expecting one input.
	return [None, '-f', input, output]

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

	# ! DEVELOPMENT:
		# Rewrite in terms of (system:command)`cat`.
	"""
	return ['empty']

def unix_compiler_collection(
		build, adapter, o_type, output, i_type, inputs,
		options=(), # Direct option injection.
		verbose=True, # Enable verbose output.
		root=False, # Designates the input as a root.
		includes:typing.Sequence[str]=(),

		verbose_flag='-v',
		language_flag='-x', standard_flag='-std',
		visibility='-fvisibility=hidden',
		color='-fcolor-diagnostics',

		output_flag='-o',
		compile_flag='-c',
		sid_flag='-isystem',
		id_flag='-I', si_flag='-include',
		debug_flag='-g',
		format_map = {
			'pic': '-fPIC',
			'pie': '-fPIE',
			'pdc': ({
				'darwin': '-mdynamic-no-pic',
			}).get(sys.platform)
		},
		co_flag='-O', define_flag='-D',
		overflow_map = {
			'wrap': '-fwrapv',
			'none': '-fstrict-overflow',
			'undefined': '-fno-strict-overflow',
		},
		dependency_options = (
			('exclude_system_dependencies', '-MM', True),
		),
		optimizations = {
			'optimal': '3',
			'metrics': '0',
			'debug': '0',
			'test': '0',
			'profile': '3',
			'delineation': '0',
		},
		empty = {}
	):
	"""
	# Construct an argument sequence for a common compiler collection command.

	# &unix_compiler_collection is the interface for constructing compilation
	# commands for a compiler collection.
	"""

	f = build.factor
	ctx = build.context
	intention = ctx.intention(None)
	lang = adapter.get('language', i_type)
	f_ctl = adapter.get('feature-control', empty).get(lang, empty)

	command = [None, compile_flag]
	if verbose:
		command.append(verbose_flag)

	# Add language flag if it's a compiler collection.
	if i_type is not None:
		command.extend((language_flag, lang))

	pl_version, pl_features = build.pl_specification(lang)
	if pl_version:
		command.append(standard_flag + '=' + pl_version)

	for feature, (f_on, f_off) in f_ctl.items():
		if feature in pl_features:
			command.append(f_on)
		else:
			command.append(f_off)

	command.append(visibility) # Encourage use of SYMBOL() define.
	command.append(color)

	# -fPIC, -fPIE or nothing. -mdynamic-no-pic for MacOS X.
	format_flags = format_map.get(o_type)
	if format_flags is not None:
		command.append(format_flags)
	else:
		if o_type is not None:
			# The selected output type did not have
			# a corresponding flag. Noting this
			# may illuminate an error.
			pass

	# Compiler optimization target: -O0, -O1, ..., -Ofast, -Os, -Oz
	co = optimizations[intention]
	command.append(co_flag + co)

	# Include debugging symbols unconditionally.
	# Filter or separate later.
	command.append(debug_flag)

	# TODO: incorporate parameter
	overflow_spec = getattr(build.factor.module, 'overflow', None)
	if overflow_spec is not None:
		command.append(overflow_map[overflow_spec])

	command.extend(adapter.get('options', ()))
	command.extend(options)

	# Include Directories; -I option.
	sid = []

	# Get the source libraries referenced by the module.
	srclib = build.references.get(('source', 'library'), ())
	for x in srclib:
		path = x.integral()
		sid.append(path)

	command.extend([id_flag + str(x) for x in sid])

	arch = build.mechanism.descriptor.get('architecture', None)
	if arch is not None:
		command.append(define_flag + 'F_TARGET_ARCHITECTURE=' + arch)

	# -D defines.
	sp = [
		define_flag + '='.join(x)
		for x in build.parameters or ()
		if x[1] is not None
	]
	command.extend(sp)

	# -U undefines.
	spo = ['-U' + x[0] for x in (build.parameters or ()) if x[1] is None]
	command.extend(spo)

	# -include files. Forced inclusion.
	for x in includes:
		command.extend((si_flag, x))

	# finally, the output file and the inputs as the remainder.
	command.extend((output_flag, output))
	command.extend(inputs)

	return command
compiler_collection = unix_compiler_collection

def python_bytecode_compiler(context, mechanism, factor,
		output, inputs,
		format=None,
		verbose=True,
		filepath=str
	):
	"""
	# Command constructor for compiling Python bytecode to an arbitrary file.
	# Executes in a distinct process.
	"""
	intention = context.intention(factor.domain)
	inf, = inputs

	command = [None, filepath(output), filepath(inf), '2' if intention == 'optimal' else '0']
	return command

def local_bytecode_compiler(
		build, adapter, o_type, output, i_type, inputs,
		verbose=True, filepath=str):
	"""
	# Command constructor for compiling Python bytecode to an arbitrary file.
	# Executes locally to minimize overhead.
	"""
	from .bin.pyc import compile_python_bytecode

	intention = build.context.intention(None)
	inf, = inputs

	command = [
		compile_python_bytecode, filepath(output), filepath(inf),
		'2' if intention == 'optimal' else '0'
	]
	return command

def windows_link_editor(transform_mechs, context, mechanisms, factor, output, inputs):
	raise RuntimeError("cl.exe linker not implemented")

def macos_link_editor(
		transform_mechanisms,
		build, adapter, o_type, output, i_type, inputs,
		partials, libraries,
		filepath=str,

		pie_flag='-pie',
		libdir_flag='-L',
		rpath_flag='-rpath',
		output_flag='-o',
		link_flag='-l',
		ref_flags={
			'weak': '-weak-l',
			'lazy': '-lazy-l',
			'default': '-l',
		},
		type_map={
			'executable': '-execute',
			'library': '-dylib',
			'extension': '-bundle',
			'partial': '-r',
		},
		lto_preserve_exports='-export_dynamic',
		platform_version_flag='-macosx_version_min',
	):
	"""
	# Command constructor for Mach-O link editor provided on Apple MacOS X systems.
	"""
	assert build.factor.domain == 'system'
	factor = build.factor
	sysarch = build.mechanism.descriptor['architecture']

	command = [None, '-t', lto_preserve_exports, platform_version_flag, '10.13.0', '-arch', sysarch]

	intention = build.context.intention(None)
	format = build.variants['format']
	ftype = build.factor.type
	mech = build.mechanism.descriptor

	loutput_type = type_map[ftype]
	command.append(loutput_type)
	if ftype == 'executable':
		if format == 'pie':
			command.append(pie_flag)

	if factor.type == 'partial':
		# Fragments use a partial link.
		command.extend(inputs)
	else:
		libs = [f for f in build.references[(factor.domain, 'library')]]
		libs.sort(key=lambda x: (getattr(x, '_position', 0), x.name))

		dirs = (x.integral() for x in libs)
		command.extend([libdir_flag+filepath(x) for x in libc.unique(dirs, None)])

		support = mech['objects'][ftype][format]
		if support is not None:
			prefix, suffix = support
		else:
			prefix = suffix = ()

		command.extend(prefix)
		command.extend(inputs)

		command.extend([link_flag+x.name for x in libs])
		command.append(link_flag+'System')

		command.extend(suffix)

		# For each source transformation mechanism, extract the link time requirements
		# that are needed by the compiler. When building targets with mixed compilers,
		# each may have their own runtime dependency that needs to be fulfilled.
		resources = set()
		for xfmech in transform_mechanisms.values():
			for x in xfmech.get('resources').values():
				resources.add(x)

		command.extend(list(resources))

	command.extend((output_flag, filepath(output)))

	return command

def _r_file_ext(r, ext):
	return r.container / (r.identifier.split('.', 1)[0] + ext)

def web_compiler_collection(context,
		output:File,
		inputs:typing.Sequence[File],
		**kw
	):
	"""
	# Command constructor for emscripten.
	"""
	output = _r_file_ext(output, '.bc')
	return unix_compiler_collection(context, output, inputs, **kw)

def web_link_editor(
		transform_mechanisms,
		context,
		output:File,
		inputs:typing.Sequence[File],

		mechanism=None,
		format=None,
		verbose=True,

		filepath=str,
		verbose_flag='-v',
		link_flag='-l', libdir_flag='-L',
		output_flag='-o',
		type_map={
			'executable': None,
			'library': '-shared',
			'extension': '-shared',
			'partial': '-r',
		},
	):
	"""
	# Command constructor for the emcc link editor.

	# [ Parameters ]

	# /output
		# The file system location to write the linker output to.

	# /inputs
		# The set of object files to link.

	# /verbose
		# Enable or disable the verbosity of the command. Defaults to &True.
	"""
	get = context.get
	f = get('factor')
	sys = get('system')
	ftype = f.type
	intention = get('variants')['intention']

	command = ['emcc']

	# emcc is not terribly brilliant; file extensions are used to determine operation.
	if ftype == 'executable':
		command.append('--emrun')

	add = command.append
	iadd = command.extend

	if verbose:
		add(verbose_flag)

	loutput_type = type_map[ftype] # failure indicates bad type parameter to libfactor.load()
	if loutput_type:
		add(loutput_type)

	if ftype != 'partial':
		sld = sys.get('library.directories', ())
		libdirs = [libdir_flag + filepath(x) for x in sld]

		sls = sys.get('library.set', ())
		libs = [link_flag + filepath(x) for x in sls]

		command.extend(map(filepath, [_r_file_ext(x, '.bc') for x in inputs]))
		command.extend(libdirs)
		command.extend(libs)
	else:
		# partial is an incremental link. Most options are irrelevant.
		command.extend(map(filepath, inputs))

	command.extend((output_flag, output))
	return command

def unix_link_editor(
		transform_mechanisms,
		build, adapter, o_type, output, i_type, inputs,
		partials, libraries, filepath=str,

		pie_flag='-pie',
		verbose_flag='-v',
		link_flag='-l',
		libdir_flag='-L',
		rpath_flag='-rpath',
		soname_flag='-soname',
		output_flag='-o',
		type_map={
			'executable': None,
			'library': '-shared',
			'extension': '-shared',
			'partial': '-r',
		},
		allow_runpath='--enable-new-dtags',
		use_static='-Bstatic',
		use_shared='-Bdynamic',
	):
	"""
	# Command constructor for the unix link editor. For platforms other than Darwin and
	# Windows, this is the default interface indirectly selected by &.development.bin.configure.

	# Traditional link editors have an insane characteristic that forces the user to decide what
	# the appropriate order of archives are. The
	# (system/command)`lorder` command was apparently built long ago to alleviate this while
	# leaving the interface to (system/command)`ld` to be continually unforgiving.

	# [ Parameters ]

	# /output
		# The file system location to write the linker output to.

	# /inputs
		# The set of object files to link.

	# /verbose
		# Enable or disable the verbosity of the command. Defaults to &True.
	"""
	factor = build.factor
	ftype = factor.type
	intention = build.variants['intention']
	format = build.variants['format']
	mech = build.mechanism.descriptor

	command = [None]
	add = command.append
	iadd = command.extend

	if mech['integrations'][None].get('name') == 'lld':
		add('-flavor')
		add('gnu')
	else:
		add(verbose_flag)

	loutput_type = type_map[ftype] # failure indicates bad type parameter to libfactor.load()
	if loutput_type:
		add(loutput_type)

	if ftype == 'partial':
		# partial is an incremental link. Most options are irrelevant.
		command.extend(map(filepath, inputs))
	else:
		libs = [f for f in build.references[(factor.domain, 'library')]]
		libs.sort(key=lambda x: (getattr(x, '_position', 0), x.name))

		dirs = (x.integral() for x in libs)
		libdirs = [libdir_flag+filepath(x) for x in libc.unique(dirs, None)]

		link_parameters = [link_flag + y for y in set([x.name for x in libs])]

		if False:
			command.extend((soname_flag, sys['abi']))

		if allow_runpath:
			# Enable by default, but allow override.
			add(allow_runpath)

		prefix, suffix = mech['objects'][ftype][format]

		command.extend(prefix)
		command.extend(map(filepath, inputs))
		command.extend(libdirs)
		command.append('-(')
		command.extend(link_parameters)
		command.append('-lc')
		command.append('-)')

		resources = set()
		for xfmech in transform_mechanisms.values():
			for x in xfmech.get('resources').values():
				resources.add(x)

		command.extend(suffix)

	command.extend((output_flag, output))
	return command

if sys.platform == 'darwin':
	link_editor = macos_link_editor
elif sys.platform in ('win32', 'win64'):
	link_editor = windows_link_editor
else:
	link_editor = unix_link_editor

def initial_factor_defines(module_fullname):
	"""
	# Generate a set of defines that describe the factor being created.
	# Takes the full module path of the factor as a string.
	"""
	modname = module_fullname.split('.')

	return [
		('FACTOR_QNAME', module_fullname),
		('FACTOR_BASENAME', modname[-1]),
		('FACTOR_PACKAGE', '.'.join(modname[:-1])),
	]

@functools.lru_cache(6)
def context_interface(path):
	"""
	# Resolves the construction interface for processing a source or performing
	# the final reduction (link-stage).
	"""

	mod, apath = Import.from_attributes(path)
	obj = importlib.import_module(str(mod))
	for x in apath:
		obj = getattr(obj, x)
	return obj

class Construction(libio.Context):
	"""
	# Construction process manager. Maintains the set of target modules to construct and
	# dispatches the work to be performed for completion in the appropriate order.

	# [ Engineering ]
		# - Rewrite as a (Transaction) Context maintaining a Flow.
		# - Generalize; flow accepts jobs and emits FlowControl events
			# describing the process. (rusage, memory, etc of process)

	# Primarily, this class traverses the directed graph constructed by imports
	# performed by the target modules being built.
	"""

	def terminate(self, by=None):
		# Manages the dispatching of processes,
		# so termination is immediate.
		self.exit()

	def __init__(self,
			context, factors,
			requirement=None,
			reconstruct=False,
			processors=4
		):
		self.reconstruct = reconstruct
		self.failures = 0
		self.exits = 0

		self.c_context = context # series of context resources for supporting subjects
		self.c_factors = factors

		# Manages the dependency order.
		self.c_sequence = sequence(factors)

		self.tracking = collections.defaultdict(list) # module -> sequence of sets of tasks
		self.progress = collections.Counter()

		self.process_count = 0 # Track available subprocess slots.
		self.process_limit = processors
		self.command_queue = collections.deque()

		self.continued = False
		self.activity = set()
		self.requirement = requirement # outputs must be newer.
		self.include_factor = Factor(None, include, None)

		super().__init__()

	def actuate(self):
		if self.reconstruct:
			self._filter = rebuild
		else:
			self._filter = functools.partial(updated, requirement=self.requirement)

		next(self.c_sequence) # generator init
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

			work, refs, deps = self.c_sequence.send(factors)
			for x in work:
				if x.module.__name__ != include.__name__:
					# Add the standard include module.
					refs[x][('source','library')].add(self.include_factor)

				self.collect(x, refs, deps.get(x, ()))
		except StopIteration:
			self.terminate()

	def collect(self, factor, references, dependents=()):
		"""
		# Collect the parameters and work to be done for processing the &factor.

		# [ Parameters ]
		# /factor
			# The &Factor being built.
		# /references
			# The set of factors referred to by &factor. Often, the
			# dependencies that need to be built in order to build the factor.
		# /dependents
			# The set of factors that refer to &factor.
		"""
		tracks = self.tracking[factor]
		ctx = self.c_context
		fm = factor.module
		refs = references[factor]
		intention = ctx.intention(None)

		common_src_params = initial_factor_defines(fm.__name__)
		if libfactor.python_extension(fm):
			# Initialize source parameters declaring the extension module's
			# access name so that full names can be properly initialized in types.
			ean = libfactor.extension_access_name(fm.__name__)
			mp = fm.__name__.rfind('.')
			tp = ean.rfind('.')

			common_src_params += [
				('MODULE_QNAME', ean),
				('MODULE_PACKAGE', ean[:tp]),
			]

		selection = ctx.select(factor.domain)
		if selection is not None:
			variants, mech = selection
		else:
			# No mechanism found.
			raise Exception("no mechanism set for factor domain in context", factor.domain)

		# Populate system factors in refs from factor requirements.
		reqs = getattr(fm, 'requirements', ())
		sf_factor_id = 0
		for sf_name in reqs:
			sf = ctx.parameters.factors(*sf_name.split('/'))
			for domain, types in sf.items():
				for ft, sf in types.items():
					for sf_int in sf:
						if sf_int is not None:
							sf_route = libroutes.File.from_absolute(sf_int)
						else:
							sf_route = None

						for sf_name in sf[sf_int]:
							refs[(domain, ft)].add(SystemFactor(
								domain = domain,
								type = ft,
								integral = sf_route,
								name = sf_name
							))

		variant_set = factor.link(variants, ctx, mech, refs, dependents)

		for src_params, (vl, key, locations) in variant_set:
			v = dict(vl)

			# The context parameters for rendering FPI.
			b_src_params = [
				('F_INTENTION', intention),
				('F_FACTOR_DOMAIN', factor.domain),
				('F_FACTOR_TYPE', factor.type),
			] + src_params + common_src_params

			if not mech.integrates() or factor.reflective:
				# For mechanisms that do not specify reductions,
				# the transformed set is the factor.
				# XXX: Incomplete; check if specific output is absent.
				locations['output'] = locations['integral']

			build = Build((
				ctx, mech, factor, refs, dependents,
				v, locations, b_src_params,
			))
			xf = list(mech.transform(build, filtered=self._filter))

			# If any commands or calls are made by the transformation,
			# rebuild the target.
			for x in xf:
				if x[0] not in ('directory', 'link'):
					f = rebuild
					break
			else:
				# Otherwise, update if out dated.
				f = self._filter

			# Collect the exact mechanisms used for reference by integration.
			xfmechs = {}
			for src in build.factor.sources():
				langname = languages.get(src.extension)
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

		fpath = factor.module.__name__ + ' '
		pidstr = ' #' + str(pid)
		formatted = {str(target): f_target_path(target)}
		printed_command = tuple(formatted.get(x, x) for x in map(str, cmd))
		message = fpath + ' '.join(printed_command) + iostr
		print(message + pidstr)

		self.sector.dispatch(sp)
		sp.atexit(functools.partial(
			self.process_exit,
			start=libtime.now(),
			descriptor=(typ, cmd, log),
			factor=factor,
			message=message,
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
					_color + factor.module.__name__ + _normal,
					pid,
					_color + str(exit_code) + _normal,
					str(duration)
				)
				print(prefix+message[message.find(' ')+1:])

		l = ''
		l += ('\n[Profile]\n')
		l += ('/factor\n\t%s\n' %(factor,))

		if log.points[-1] != 'reduction':
			l += ('/subject\n\t%s\n' %('/'.join(log.points),))
		else:
			l += ('/subject\n\treduction\n')

		l += ('/pid\n\t%d\n' %(pid,))
		l += ('/status\n\t%s\n' %(str(status),))
		l += ('/start\n\t%s\n' %(start.select('iso'),))
		l += ('/stop\n\t%s\n' %(libtime.now().select('iso'),))

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