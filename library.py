"""
# Management of factor processing instructions for creating system binaries.

# [ Properties ]

# /library_extensions
	# Used by &library_filename to select the appropriate extension
	# for `system.library` and `system.extension` factors.

# /selections
	# A mapping providing the selected role to use for the factor module.

# /python_triplet
	# The `-` separated strings representing the currently executing Python context.
	# Used to construct directories for Python extension builds.

# /bytecode_triplet
	# The `-` separated strings representing the bytecode used by the executing Python
	# context.
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
from . import library as libdev

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

# Used as the context name for extension modules.
python_triplet = python_context(
	sys.implementation.name, sys.version_info, sys.abiflags, sys.platform
)

bytecode_triplet = python_context(
	sys.implementation.name, sys.version_info, '', 'bytecode'
)

selections = None

_factor_role_patterns = None
_factor_roles = None # exact matches

def select(module, role, context=None):
	"""
	# Designate that the given role should be used for the identified &package and its content.

	# &select should only be used during development or development related operations. Notably,
	# selecting the role for a given package during the testing of a project.

	# It can also be used for one-off debugging purposes where a particular target is of interest.
	"""
	global _factor_roles, _factor_role_patterns
	if _factor_roles is None:
		_factor_roles = {}

	if module.endswith('.'):
		path = tuple(module.split('.')[:-1])
		from ..computation import libmatch

		if _factor_role_patterns is None:
			_factor_role_patterns = libmatch.SubsequenceScan([path])
		else:
			x = list(_factor_role_patterns.sequences)
			x.append(path)
			_factor_role_patterns = libmatch.SubsequenceScan(x)

		_factor_roles[module[:-1]] = role
	else:
		# exact
		_factor_roles[module] = role

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

	# [ Return ]
	#
		# /&bool
			# Whether the file was updated or not.
	#
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
		return (False, 'update condition was not present')

	return (True, cache_file)

def references(factors):
	container = collections.defaultdict(set)
	for f in factors:
		container[f.pair].add(f)
	return container

class iFactor(object):
	"""
	# Imaginary Factor. Used by probes to create virtual dependencies representing
	# an already constructed Factor.
	"""

	@classmethod
	def headers(Class, path):
		return Class(
			type = 'source',
			dynamics = 'library',
			name = None,
			integral = path
		)

	@classmethod
	def library(Class, path, name, type='system'):
		return Class(
			type = type,
			dynamics = 'library',
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

class Factor(object):
	"""
	# A Factor of a development environment; similar to "targets" in IDEs.

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
		# cases where a simulated Factor was formed.
		"""
		if hasattr(module, '__factor__'):
			return module.__factor__
		return Class(None, module, None)

	@property
	@functools.lru_cache(32)
	def fullname(self):
		return self.route.fullname

	def __str__(self):
		struct = "factor://{0.type}.{scheme}/{0.fullname}#{0.module_file.fullpath}"
		return struct.format(self, scheme=self.dynamics[:3])

	@property
	def name(self):
		return self.route.identifier

	@property
	def type(self):
		try:
			return self.module.__factor_type__
		except AttributeError:
			# python.library
			return 'python'

	@property
	def dynamics(self):
		try:
			return self.module.__factor_dynamics__
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
		return (self.type, self.dynamics)

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
		is_probe = libfactor.probe
		ModuleType = types.ModuleType

		for v in factor.module.__dict__.values():
			if not isinstance(v, ModuleType):
				continue
			if not hasattr(v, '__factor_type__'):
				continue
			if not hasattr(v, '__factor_dynamics__'):
				# Factor, but no dynamics means that
				# it has no transformation to perform.
				continue

			yield Factor(None, v, None)

	def report(self, context, mechanism, factor):
		"""
		# Probe abstraction used to access the module's report function.
		"""
		if getattr(self.module, 'reflective', False):
			# Unconditionally use report directly for reflective modules.
			return self.module.report(self, context, mechanism, factor)
		else:
			return probe_retrieve(self, context, mechanism, None)

	def aggregate(self, references, variants, context, mechanism, dynamics='probe'):
		"""
		# Aggregate the probe reports.
		"""

		src_params = []
		variants = {}
		factors = []

		for p in references[(self.type, dynamics)]:
			build_params, params, pfactors = p.report(context, mechanism, self)
			src_params.extend(params)
			variants.update(build_params)

			# Attach origin for build debugging.
			for ifactor in pfactors:
				ifactor.origin = p
			factors.extend(pfactors)

		return variants, src_params, factors

	def formats(self, mechanism, dependents):
		"""
		# Yield the formats to build based on the given mechanism, dependents and
		# the factor's dynamics.

		# For factors other than `'fragment'`, this is always a single item.
		"""

		fformats = mechanism.descriptor['formats'] # code types used by the object types

		if self.dynamics == 'fragment':
			# For fragments, the dependents decide
			# the format set to build. If no format is designated,
			# the default is presumed.
			default = fformats.get('fragment') or fformats[None]

			for x in dependents:
				yield fformats.get(x.dynamics, default)
		else:
			# For system factors, this determines PIC/PIE/Unspecified.
			yield fformats.get(self.dynamics) or fformats[None]

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
			# Prepare for probe report extraction.
			vars = dict(variants)
			vars['format'] = fmt

			bp, sp, ifs = self.aggregate(refs, variants, context, mechanism)
			vars.update(bp)
			# XXX: This doesn't work for fragments.
			for f in ifs:
				refs[(f.type, f.dynamics)].add(f)

			yield sp, self.fpi_initialize(vars, format=fmt)

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
	# with a Factor.

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
			tfe.get(factor.dynamics) or \
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

		yield ('directory', ftr)
		if not f.reflective:
			yield ('link', rr, ftr / 'pf.lnk')

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
				yield ('directory', x)

	def adaption(self, build, type, source, phase='transformations'):
		"""
		# Select the adapter of the mechanism for the given source.

		# Adapters with inheritance will be cached by the mechanism.
		"""
		acache = self.cache
		aset = self.descriptor[phase]

		# Mechanisms support explicit inheritance.
		if (phase, type) in acache:
			return acache[(phase, type)]

		if type in aset:
			key = type
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
		acache[(phase, type)] = cmech

		return cmech

	def transform(self, build, filtered=rebuild):
		"""
		# Transform the sources using the mechanisms defined in &context.
		"""
		global languages, include

		f = build.factor
		ftype = f.type
		loc = build.locations
		logs = loc['log']
		ctxname = build.variants['name']
		fmt = build.variants['format']

		mechanism = build.mechanism.descriptor
		ignores = mechanism.get('ignore-extensions', ())

		commands = []
		for src in f.sources():
			fnx = src.extension
			if ctxname != 'inspect' and fnx in ignores or src.identifier.startswith('.'):
				# Ignore header files and dot-files for non-inspect contexts.
				continue
			obj = File(loc['output'], src.points)

			if filtered((obj,), (src,)):
				continue

			logfile = File(loc['log'], src.points)

			src_type = languages.get(src.extension)
			out_format = mechanism['formats'][f.dynamics]

			adapter = self.adaption(build, src_type, src, phase='transformations')
			xf = context_interface(adapter['interface'])

			# Compilation to out_format for integration.
			seq = list(xf(build, adapter, out_format, obj, src_type, (src,)))

			yield self.formulate(obj, logfile, adapter, seq)

	def formulate(self, route, logfile, adapter, sequence, python=sys.executable):
		"""
		# Convert a generated instruction into a form accepted by &Construction.
		"""
		method = adapter.get('method')
		command = adapter.get('command')
		redirect = adapter.get('redirect')

		if method == 'python':
			sequence[0:1] = (python, '-m', command)
		elif method == 'internal':
			return ('call', sequence, logfile)
		else:
			# Adapter interface leaves this as None or a relative name.
			# Update to absolute path entered into adapter.
			sequence[0] = command

		if redirect:
			return ('execute-redirection', sequence, logfile, route)
		else:
			return ('execute', sequence, logfile)

	def integrate(self, build, filtered=rebuild, sys_platform=sys.platform):
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

		fragments = [x for x in build.references[(f.type, 'fragment')]]
		if filtered((rr,), objects):
			return

		adapter = self.adaption(build, f.dynamics, objects, phase='integrations')

		# Mechanisms with a configured root means that the
		# transformed objects will be referenced by the root file.
		root = adapter.get('root')
		if root is not None:
			objects = [objdir / root]

		# Libraries and fragments of the same type are significant.
		libraries = [x for x in build.references[(f.type, 'library')]]

		xf = context_interface(adapter['interface'])
		seq = xf(build, adapter, f.dynamics, rr, fmt, objects, fragments, libraries)
		logfile = loc['log'] / 'Integration.log'

		yield self.formulate(rr, logfile, adapter, seq)

xml_namespaces = {
	'lc': 'http://fault.io/xml/dev/fpi',
	'd': 'http://fault.io/xml/data',
}

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

class Context(object):
	"""
	# A sequence of mechanism sets, Construction Context, that
	# can be used to supply a given build with tools for factor
	# processing.
	"""

	def __init__(self, sequence):
		self.sequence = sequence or ()

	@functools.lru_cache(8)
	def purpose(self, ftype):
		"""
		# The purpose of the Context for the given factor type.

		# While usually consistent across the mechanism sets, there are
		# cases where an implementation chooses to reduce the purposes
		# where it is known that the builds are consistent. Python bytecode
		# being the notable case where (dev:purpose)`debug` is consistent
		# with (dev:purpose)`test` and (dev:purpose)`measure`.

		# Presumes optimal if the mechanism sets did not define a purpose.
		# This is used for compensating cases where the generated mechanism
		# sets have consistent purpose for automated builds.
		"""
		for x in self.sequence:
			if ftype not in x:
				continue

			p = x['variants'].get('purpose')
			if p is not None:
				return p
		else:
			return 'optimal'

	@functools.lru_cache(8)
	def select(self, ftype):
		for x in self.sequence:
			if ftype in x:
				return x['variants'], Mechanism(x[ftype])
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

		# XInclude is how imports/refs to other contexts are managed.
		xml.xinclude()
		d = xml.xpath('/lc:libconstruct/lc:context', namespaces=xml_namespaces)

		# Merge context data in the order they appear.
		for x in d:
			# Attributes on the context element define the variant.
			variants.update(x.attrib)
			data = libxml.Data.structure(list(x)[0])
			merge(context, data)

		context['variants'] = variants

		return xml, context

	@classmethod
	def from_environment(Class, envvar="FPI_MECHANISMS"):
		mech_refs = os.environ.get(envvar, '').split(os.pathsep)
		seq = []
		for mech in mech_refs:
			xml, ctx = Class.load_xml(File.from_absolute(mech))
			seq.append(ctx)

		return Class(seq)

# Specifically for identifying files to be compiled and how.
extensions = {
	'c': ('c',),
	'c++': ('c++', 'cpp', 'hh'),
	'objective-c': ('m',),

	# C++ without rtti and exceptions.
	'c++[rtti exceptions]': ('cxx',),

	'ada': ('ads', 'ada'),
	'assembly': ('asm',),
	'bitcode': ('bc',), # clang
	'haskell': ('hs', 'hsc'),
	'd': ('d',),
	'rust': ('rs',),
	'header': ('h',), # Purposefully ambiguous. (Can be C/C++/Obj-C)
	'c++.header': ('H', 'hpp', 'hxx'),

	'python': ('py',),
	'bytecode.python': ('pyo', 'pyc',),
	'pyrex.python': ('pyx',),

	'javascript': ('json', 'javascript', 'js'),
	'css': ('css',),
	'xml': ('xml', 'xsl', 'rdf', 'rng', 'htm', 'html'),
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

	# [ Return ]

	# A pair consisting of the fabricated module and the next set of packages to process.
	"""
	global libfactor
	pkgs, modules = route.subnodes()

	if not route.exists():
		raise ValueError(route) # module does not exist?

	modules.append(route)
	sources = [
		x.__class__(x.container, (x.identifier,))
		for x in [x.file() for x in modules if x.exists()]
		if x.extension == 'py'
	]
	pkgfile = route.file()

	mod = types.ModuleType(str(route), "Simulated composite factor for bytecode compilation")
	mod.__factor_type__ = 'bytecode.python'
	mod.__factor_dynamics__ = 'library' # Truthfully, a [python] Package.
	mod.__factor_sources__ = sources # Modules in the package.
	mod.__factor_context__ = bytecode_triplet
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
	# The (python:attribute)`name` attribute on a target module provides an explicit
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
	if module.__factor_type__.endswith('.library'):
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

def concatenation(build, adapter, o_type, output, i_type, inputs,
		verbose=True,
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
		}
	):
	"""
	# Construct an argument sequence for a common compiler collection command.

	# &unix_compiler_collection is the interface for constructing compilation
	# commands for a compiler collection.
	"""

	f = build.factor
	fdyna = f.dynamics
	purpose = build.variants['purpose']
	lang = adapter.get('language', i_type)

	command = [None, compile_flag]
	if verbose:
		command.append(verbose_flag)

	# Add language flag if it's a compiler collection.
	if i_type is not None:
		command.extend((language_flag, lang))

	if 'standards' in f.module.__dict__:
		standards = f.module.standards
	elif 'standards' in adapter:
		standards = adapter['standards']
	else:
		standards = None
		standard = None

	if standards is not None:
		standard = standards.get(lang, None)

	if standard is not None and standard_flag is not None:
		command.append(standard_flag + '=' + standard)

	command.append(visibility) # Encourage use of SYMBOL() define.
	command.append(color)

	# -fPIC, -fPIE or nothing. -mdynamic-no-pic for MacOS X.
	format_flags = format_map.get(o_type)
	if format_flags is not None:
		command.append(format_flags)

	# Compiler optimization target: -O0, -O1, ..., -Ofast, -Os, -Oz
	co = optimizations[purpose]
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

	# coverage options for metrics and profile roles.
	if purpose in {'metrics', 'profile'}:
		command.extend(('-fprofile-instr-generate', '-fcoverage-mapping'))

	# Include Directories; -I option.
	sid = []

	# Get the source libraries referenced by the module.
	srclib = build.references.get(('source', 'library'), ())
	for x in srclib:
		sid.append(x.integral())

	command.extend([id_flag + str(x) for x in sid])

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
	# TODO
	sis = ()
	for x in sis:
		command.extend((si_flag, x))

	command.extend(options)

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
	"""
	purpose = context.purpose(factor.type)
	inf, = inputs

	command = [None, filepath(output), filepath(inf), '2' if purpose == 'optimal' else '0']
	return command

def local_bytecode_compiler(
		build, adapter, o_type, output, i_type, inputs,
		verbose=True, filepath=str):
	"""
	# Command constructor for compiling Python bytecode to an arbitrary file.
	"""
	from .bin.pyc import compile_python_bytecode

	purpose = build.variants['purpose']
	inf, = inputs

	command = [
		compile_python_bytecode, filepath(output), filepath(inf),
		'2' if purpose == 'optimal' else '0'
	]
	return command

def windows_link_editor(context, mechanisms, factor, output, inputs):
	raise RuntimeError("cl.exe linker not implemented")

def macosx_link_editor(
		build, adapter, o_type, output, i_type, inputs,
		fragments, libraries, filepath=str,

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
			'fragment': '-r',
		},
		lto_preserve_exports='-export_dynamic',
		platform_version_flag='-macosx_version_min',
	):
	"""
	# Command constructor for Mach-O link editor provided on Apple MacOS X systems.
	"""
	assert build.factor.type == 'system'
	factor = build.factor

	command = [None, '-t', lto_preserve_exports, platform_version_flag, '10.11.0',]

	purpose = build.variants['purpose']
	format = build.variants['format']
	fdyna = build.factor.dynamics
	mxf = build.mechanism.descriptor['transformations'][None]
	mech = build.mechanism.descriptor

	loutput_type = type_map[fdyna]
	command.append(loutput_type)
	if fdyna == 'executable':
		if format == 'pie':
			command.append(pie_flag)

	if factor.dynamics == 'fragment':
		# Fragments use a partial link.
		command.extend(inputs)
	else:
		libs = [f for f in build.references[(factor.type, 'library')]]

		dirs = set([x.integral() for x in libs])
		dirs.discard(None)
		command.extend([libdir_flag+filepath(x) for x in dirs])

		support = mech['objects'][fdyna][format]
		if support is not None:
			prefix, suffix = support
		else:
			prefix = suffix = ()

		command.extend(prefix)
		command.extend(inputs)

		command.extend([link_flag+x.name for x in libs])
		command.append(link_flag+'System')

		command.extend(suffix)
		if purpose in {'metrics', 'profile'}:
			command.append(mxf['resources']['profile'])

		command.append(mxf['resources']['builtins'])

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

def web_link_editor(context,
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
			'fragment': '-r',
		},
	):
	"""
	# Command constructor for the emcc link editor.

	# [Parameters]

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
	fdyna = f.dynamics
	purpose = get('variants')['purpose']

	command = ['emcc']

	# emcc is not terribly brilliant; file extensions are used to determine operation.
	if fdyna == 'executable':
		command.append('--emrun')

	add = command.append
	iadd = command.extend

	if verbose:
		add(verbose_flag)

	loutput_type = type_map[fdyna] # failure indicates bad type parameter to libfactor.load()
	if loutput_type:
		add(loutput_type)

	if fdyna != 'fragment':
		sld = sys.get('library.directories', ())
		libdirs = [libdir_flag + filepath(x) for x in sld]

		sls = sys.get('library.set', ())
		libs = [link_flag + filepath(x) for x in sls]

		command.extend(map(filepath, [_r_file_ext(x, '.bc') for x in inputs]))
		command.extend(libdirs)
		command.extend(libs)
	else:
		# fragment is an incremental link. Most options are irrelevant.
		command.extend(map(filepath, inputs))

	command.extend((output_flag, output))
	return command

def unix_link_editor(
		build, adapter, o_type, output, i_type, inputs,
		fragments, libraries, filepath=str,

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
			'fragment': '-r',
		},
		allow_runpath='--enable-new-dtags',
		use_static='-Bstatic',
		use_shared='-Bdynamic',
	):
	"""
	# Command constructor for the unix link editor. For platforms other than &(Darwin) and
	# &(Windows), this is the default interface indirectly selected by &.development.bin.configure.

	# Traditional link editors have an insane characteristic that forces the user to decide what
	# the appropriate order of archives are. The
	# (system:command)`lorder` command was apparently built long ago to alleviate this while
	# leaving the interface to (system:command)`ld` to be continually unforgiving.

	# [Parameters]

	# /output
		# The file system location to write the linker output to.

	# /inputs
		# The set of object files to link.

	# /verbose
		# Enable or disable the verbosity of the command. Defaults to &True.
	"""
	factor = build.factor
	fdyna = factor.dynamics
	purpose = build.variants['purpose']
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

	loutput_type = type_map[fdyna] # failure indicates bad type parameter to libfactor.load()
	if loutput_type:
		add(loutput_type)

	if fdyna == 'fragment':
		# fragment is an incremental link. Most options are irrelevant.
		command.extend(map(filepath, inputs))
	else:
		sld = []
		libdirs = [libdir_flag + filepath(x) for x in sld]

		sls = []
		libs = [link_flag + filepath(x) for x in sls]

		if False:
			command.extend((soname_flag, sys['abi']))

		if allow_runpath:
			# Enable by default, but allow override.
			add(allow_runpath)

		prefix, suffix = mech['objects'][fdyna][format]

		command.extend(prefix)
		command.extend(map(filepath, inputs))
		command.extend(libdirs)
		command.append('-(')
		command.extend(libs)
		command.append('-)')

		resources = mech['transformations'][None]['resources']

		if purpose in {'metrics', 'profile'}:
			command.append(resources['profile'])

		command.append(resources['builtins'] or '-lgcc')
		command.extend(suffix)

	command.extend((output_flag, output))
	return command

if sys.platform == 'darwin':
	link_editor = macosx_link_editor
elif sys.platform in ('win32', 'win64'):
	link_editor = windows_link_editor
else:
	link_editor = unix_link_editor

def probe_retrieve(probe, context, mechanism, key):
	"""
	# Retrieve the stored data collected by the sensor.
	"""

	rf = probe_cache(probe, context)
	if not rf.exists():
		return None

	import pickle
	with rf.open('rb') as f:
		try:
			report = pickle.load(f)
			return report
		except (FileNotFoundError, EOFError):
			return ((), (), ())

def probe_record(probe, context, key, report):
	"""
	# Record the report for subsequent runs.
	"""

	rf = probe_cache(probe, context)
	rf.init('file')

	import pickle
	with rf.open('wb') as f:
		pickle.dump(report, f)

def probe_cache(probe, context):
	"""
	# Return the route to the probe's recorded report.
	"""
	return probe.cache_directory / (probe.route.identifier + '.pc')

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

class Construction(libio.Processor):
	"""
	# Construction process manager. Maintains the set of target modules to construct and
	# dispatches the work to be performed for completion in the appropriate order.

	# ! DEVELOPMENT: Pending
		# - Rewrite as a Flow.
		# - Generalize; flow accepts jobs and emits FlowControl events
			# describing the process. (rusage, memory, etc of process)

	# ! DEVELOPER:
		# Primarily, this class traverses the directed graph constructed by imports
		# performed by the target modules being built.

		# Refactoring could yield improvements; notably moving the work through a Flow
		# in order to leverage obstruction signalling.
	"""

	def __init__(self,
			context, factors,
			requirement=None,
			reconstruct=False,
			processors=4
		):
		self.reconstruct = reconstruct
		self.failures = 0

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
		# Collect all the work to be done for processing the factor.
		"""
		tracks = self.tracking[factor]
		ctx = self.c_context
		fm = factor.module
		refs = references[factor]

		if factor.pair == ('system', 'probe'):
			# Needs to be transformed into a work set.
			# Probes are deployed per dependency.
			if hasattr(fm, 'deploy') and getattr(fm, 'reflective', False) == False:
				# If the probe does not designate deployment or is explicitly
				# stated to be reflective, do not initiate a deployment.
				probe_set = [('probe', factor, x) for x in dependents]
				tracks.append(probe_set)
		else:
			variants, mech = ctx.select(factor.type)
			variant_set = factor.link(variants, ctx, mech, refs, dependents)

			for src_params, (vl, key, locations) in variant_set:
				v = dict(vl)

				# The context parameters for rendering FPI.
				b_src_params = [
					('F_PURPOSE', variants['purpose']),
					('F_DYNAMICS', factor.dynamics),
				] + src_params

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

				fi = list(mech.integrate(build, filtered=f))
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

	def probe_execute(self, factor, instruction):
		assert instruction[0] == 'probe'

		sector = self.sector
		dep = instruction[2]
		module = factor.module

		if getattr(module, 'key', None) is not None:
			# Get the storage key for the probe
			key = module.key(factor, self.c_context, dep)
		else:
			key = None

		report = probe_retrieve(factor, self.c_context, None, key)

		if report is not None:
			# Needed report is cached.
			self.progress[factor] += 1
		else:
			f = lambda x: self.probe_dispatch(factor, self.c_context, dep, key, x)
			t = libio.Thread(f)
			self.sector.dispatch(t)

	def probe_dispatch(self, factor, context, dep, key, tproc):
		# Executed in thread.
		sector = self.controller # Allow libio.context()

		report = factor.module.deploy(factor, context, dep)
		self.ctx_enqueue_task(
			functools.partial(
				self.probe_exit,
				tproc,
				context=context,
				factor=factor,
				report=report,
				key=key
			),
		)

	def probe_exit(self, processor, context=None, factor=None, report=None, key=None):
		self.progress[factor] += 1
		self.activity.add(factor)

		rreport = probe_retrieve(factor, context, None, key)
		probe_record(factor, context, key, report)

		if self.continued is False:
			# Consolidate loading of the next set of processors.
			self.continued = True
			self.ctx_enqueue_task(self.continuation)

	def process_execute(self, instruction):
		factor, ins = instruction
		typ, cmd, log, *out = ins
		if typ == 'execute-redirection':
			stdout = str(out[0])
		else:
			stdout = os.devnull

		assert typ in ('execute', 'execute-redirection')

		strcmd = tuple(map(str, cmd))

		pid = None
		with log.open('wb') as f:
			f.write(b'[Command]\n')
			f.write(' '.join(strcmd).encode('utf-8'))
			f.write(b'\n\n[Standard Error]\n')

			ki = libsys.KInvocation(str(cmd[0]), strcmd, environ=dict(os.environ))
			with open(os.devnull, 'rb') as ci, open(stdout, 'wb') as co:
				pid = ki(fdmap=((ci.fileno(), 0), (co.fileno(), 1), (f.fileno(), 2)))
				sp = libio.Subprocess(pid)

		print(' '.join(strcmd) + ' #' + str(pid))
		self.sector.dispatch(sp)
		sp.atexit(functools.partial(self.process_exit, start=libtime.now(), descriptor=(typ, cmd, log), factor=factor))

	def process_exit(self, processor, start=None, factor=None, descriptor=None):
		assert factor is not None
		assert descriptor is not None
		self.progress[factor] += 1
		self.process_count -= 1
		self.activity.add(factor)

		typ, cmd, log = descriptor
		pid, status = processor.only
		exit_method, exit_code, core_produced = status
		if exit_code != 0:
			self.failures += 1

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
			if x[0] in ('execute', 'execute-redirection'):
				self.command_queue.append((factor, x))
			elif x[0] == 'directory':
				for y in x[1:]:
					y.init('directory')
				self.progress[factor] += 1
			elif x[0] == 'link':
				cmd, src, dst = x
				dst.link(src)
				self.progress[factor] += 1
			elif x[0] == 'call':
				try:
					seq = x[1]
					seq[0](*seq[1:])
					if logfile.exists():
						logfile.void()
				except BaseException as err:
					from traceback import format_exception
					logfile = x[-1]
					out = format_exception(err.__class__, err, err.__traceback__)
					logfile.store('[Exception]\n#!/traceback\n\t', 'w')
					logfile.store('\t'.join(out).encode('utf-8'), 'ba')
				self.progress[factor] += 1
			elif x[0] == 'probe':
				self.probe_execute(factor, x)
			else:
				print('unknown instruction', x)

		if self.progress[factor] >= len(self.tracking[factor][0]):
			self.activity.add(factor)

			if self.continued is False:
				self.continued = True
				self.ctx_enqueue_task(self.continuation)

	def terminate(self, by=None):
		# Manages the dispatching of processes,
		# so termination is immediate.
		self.exit()
