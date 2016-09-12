"""
Management of target construction jobs for creating system [context] executable,
libraries, and extensions.

The effects that &.libconstruct causes are heavily influenced by the Construction Context.
The Construction Context is defined as a set of roles which ultimately determine the
necessary procedures for constructing a target.

[ Properties ]

/variants
	Dictionary of construction roles used by libconstruct to manage different
	transformations of &libdev.Sources modules.

/library_extensions
	Used by &library_filename to select the appropriate extension
	for `system.library` and `system.extension` factors.

/selected_context
	Construction context to load from. Variant is specified after `'#'`.

/selections
	A mapping providing the selected role to use for the factor module.

/python_triplet
	The `-` separated strings representing the currently executing Python context.
	Used to construct directories for Python extension builds.

/bytecode_triplet
	The `-` separated strings representing the bytecode used by the executing Python
	context.

[ Environment ]

/libfpi_context
	Construction Context to build with. Absolute path to XML or a relative
	path designating the variant-set pair.

/libfpi_directory
	Path to the collection of construction context sets.
"""
import os
import sys
import copy
import functools
import itertools
import collections
import contextlib
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

fpi_addressing = libfs.Hash('fnv1a_32', depth=1, length=4)

selected_context = 'host#optimal'

library_extensions = {
	'msw': 'dll',
	'win32': 'dll',
	'darwin': 'dylib',
	'unix': 'so',
}

def library_filename(platform, name):
	"""
	Construct a dynamic library filename for the given platform.
	"""
	global library_extensions
	return 'lib' + name.lstrip('lib') + '.' + library_extensions.get(platform, 'so')

def python_context(implementation, version_info, abiflags, platform):
	"""
	Construct the triplet representing the Python context for the platform.
	Used to define the construction context for Python extension modules.
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
	Designate that the given role should be used for the identified &package and its content.

	&select should only be used during development or development related operations. Notably,
	selecting the role for a given package during the testing of a project.

	It can also be used for one-off debugging purposes where a particular target is of interest.
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

def scan_modification_times(factor, aggregate=max):
	"""
	Scan the factor's sources for the latest modification time.
	"""
	dirs, files = libfactor.sources(factor).tree()
	del dirs

	glm = libroutes.File.get_last_modified
	return aggregate(x for x in map(glm, files))

def variant(module, role='optimal', context=None):
	"""
	Get the configured role for the given module path.
	"""
	global _factor_roles, _factor_role_patterns

	path = str(module)

	if _factor_roles is None:
		return role

	if path in _factor_roles:
		return _factor_roles[path]

	if _factor_role_patterns is not None:
		# check for pattern
		path = _factor_role_patterns.get(tuple(path.split('.')))
		return _factor_roles['.'.join(path)]

	return default_role

def work_directory(import_route:Import, cache='__pycache__', name='.fpi'):
	"""
	Get the relevant work directory inside the associated
	(system:relpath)`__pycache__/.fpi` directory.
	"""

	# Get a route to the FPI build set in __pycache__.
	return import_route.file().container / '__pycache__' / name

def fpi_work_key(variants):
	"""
	Calculate the key from the sorted list.

	Sort function is of minor importance, there is no warranty
	of consistent accessibility across platform.
	"""
	vl = list(variants.items())
	vl.sort()
	return ';'.join('='.join((k,v)) for k,v in vl).encode('utf-8')

def context_work_route(fpi, variants):
	"""
	Get the work directory of the factor.
	"""

	wd = libfs.Dictionary.use(fpi, addressing=fpi_addressing)
	k = fpi_work_key(variants)
	r = wd.route(k)

	return r

def context_work(import_route, variants):
	"""
	Get the work directory of the factor.
	"""

	fpi = work_directory(import_route)
	return context_work_route(fpi, variants)

def reduction(import_route, variants):
	"""
	Get the reduction for a construction context.
	"""

	ftr = context_work(import_route, variants) / 'ftr'
	return ftr

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
	Merge the given &source into &parameters applying merge functions
	defined in &operations. Dictionaries are merged using recursion.
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

xml_namespaces = {
	'lc': 'http://fault.io/xml/dev/fpi',
	'd': 'http://fault.io/xml/data',
}

def root_context_directory(env='FPI_DIRECTORY'):
	"""
	Return the &libroutes.File instance to the root context.
	By default, this is (fs:path)`~/.fault/fpi`, but can
	be overridden by the (system:environment)`FPI_DIRECTORY` variable.

	The result of this should only be cached in order to maintain a consistent
	perspective; this function polls the environment for the appropriate version.

	[ Parameters ]
	/env
		The environment variable name to use when looking for an override
		of the user's home.
	"""
	global os
	if env in os.environ:
		return libroutes.File.from_absolute(os.environ[env])

	return libroutes.File.home() / '.fault' / 'fpi'

def load_context(route:libroutes.File):
	"""
	Load the context selected by &route and process the 
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

def root_context(directory, selection, role):
	xf = directory / (selection or 'host') / (role + '.xml')
	if not xf.exists():
		return None, {}

	return load_context(xf)

def contexts(purpose, primary='host', fallback='static', environment=()):
	doc, p_ctx = root_context(root_context_directory(), primary, purpose)
	sd, static_ctx = root_context(root_context_directory(), fallback, purpose)

	p = [p_ctx]
	p.extend([load_context(libroutes.File.from_absolute(x))[1] for x in environment])
	p.append(static_ctx)

	return tuple(p)

# Specifically for identifying files to be compiled and how.
extensions = {
	'c': ('c','h'),
	'c++': ('c++', 'cxx', 'cpp', 'hh'),
	'objective-c': ('m',),
	'ada': ('ads', 'ada'),
	'assembly': ('asm',),
	'bitcode': ('bc',), # clang
	'haskell': ('hs', 'hsc'),
	'python': ('py',),

	'javascript': ('json', 'javascript', 'js'),
	'css': ('css',),
	'xml': ('xml', 'xsl', 'rdf', 'rng'),
}

languages = {}
for k, v in extensions.items():
	for y in v:
		languages[y] = k
del k, y, v

def simulate_composite(route):
	"""
	Given a Python package route, fabricate a composite factor in order
	to process Python module sources.

	[ Returns ]

	A pair consisting of the fabricated module and the next set of packages to process.
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
	mod.__factor_type__ = 'python.bytecode'
	mod.__factor_dynamics__ = 'library'
	mod.__factor_sources__ = sources
	mod.__factor_context__ = bytecode_triplet
	mod.__file__ = str(pkgfile)

	return mod, pkgs

def gather_simulations(contexts, packages:typing.Sequence[Import]):
	# Get the simulations for the bytecode files.
	next_set = packages

	while next_set:
		current_set = next_set
		next_set = []

		for pkg in current_set:
			mod, adds = simulate_composite(pkg)
			next_set.extend(adds)

			mech, ctx = initialize(contexts, mod, ())
			yield mech, ctx

# The extension suffix to use for *this* Python installation.
python_extension_suffix = importlib.machinery.EXTENSION_SUFFIXES[0]

def link_extension(route, factor):
	"""
	Link an inducted Python extension module so that the constructed binary
	can be used by (python:statement)`import`.

	Used by &.bin.induct after copying the target's factor to the &libfactor.

	[ Parameters ]
	/route
		The &Import selecting the composite factor to induct.
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

def collect(module):
	"""
	Return the set of dependencies that the given module has.
	"""
	global libfactor, libroutes, types
	is_composite = libfactor.composite
	is_probe = libfactor.probe

	ModuleType = types.ModuleType
	for v in module.__dict__.values():
		if not isinstance(v, ModuleType) or not hasattr(v, '__factor_type__'):
			continue

		if getattr(v, '__factor_composite__', None):
			# Override for pseudo modules/factors.
			yield v
		else:
			i = Import.from_fullname(v.__name__)
			if is_composite(i) or is_probe(v):
				yield v

def traverse(working, tree, inverse, module):
	"""
	Invert the directed graph of dependencies from the target modules.

	System factor modules import their dependencies into their global
	dictionary forming a directed graph. The imported factor modules are
	identified as dependencies that need to be constructed in order
	to process the subject module. The inverted graph is constructed to manage
	completion signalling for processing purposes.
	"""
	global collect

	deps = set(collect(module))
	if not deps:
		# No dependencies, add to working set and return.
		working.add(module)
		return
	elif module in tree:
		# It's already been traversed in a previous run.
		return

	# dependencies present, assign them inside the tree.
	tree[module] = deps

	for x in deps:
		inverse[x].add(module)
		traverse(working, tree, inverse, x)

def sequence(modules):
	"""
	Generator maintaining the state of sequencing a traversed factor depedency
	graph. This generator emits factors as they are ready to be processed and receives
	factors that have completed processing.

	When a set of dependencies has been processed, they should be sent to the generator
	as a collection; the generator identifies whether another set of modules can be
	processed based on the completed set.

	Completion is an abstract notion, &sequence has no requirements on the semantics of
	completion and its effects; it merely communicates what can now be processed based
	completion state.
	"""
	global collections

	tree = dict()
	inverse = collections.defaultdict(set)
	working = set()
	for factor in modules:
		traverse(working, tree, inverse, factor)

	new = working

	while working:
		completion = (yield tuple(new), {x: tuple(inverse[x]) for x in new if inverse[x]})
		new = set() # &completion triggers new additions to &working

		for module in (completion or ()):
			# completed.
			working.discard(module)

			for deps in inverse[module]:
				tree[deps].discard(module)
				if not tree[deps]:
					# Add to both; new is the set reported to caller,
					# and working tracks when the graph has been fully sequenced.
					new.add(deps)
					working.add(deps)
					del tree[deps]

def identity(module):
	"""
	Discover the base identity of the target.

	Primarily, used to identify the proper basename of a library.
	The (python:attribute)`name` attribute on a target module provides an explicit
	override. If the `name` is not present, then the first `'lib'` prefix
	is removed from the module's name if any. The result is returned as the identity.
	The removal of the `'lib'` prefix only occurs when the target factor is a
	`'system.library'`.
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
	A transformation that can be assigned to a subject's mechanism
	in order to describe it as being disabled.
	"""
	return ()

def transparent(context, output, inputs,
		mechanism=None,
		language=None,
		format=None,
		verbose=True,
	):
	"""
	Create links from the input to the output; used for zero transformations.
	"""
	input, = inputs # Rely on exception from unpacking.
	#return ('link', input, output)
	return [None, '-f', input, output]

def concatenation(context, output, inputs,
		mechanism=None,
		language=None,
		format=None,
		verbose=True,
	):
	"""
	Create the factor by concatenating the files. Only used in cases
	where the order of concatentation is already managed or irrelevant.

	Requires 'execute-redirect'.
	"""
	return ['cat'] + list(inputs)

def empty(context, output, inputs,
		mechanism=None,
		language=None,
		format=None,
		verbose=True,
	):
	"""
	Create the factor by executing a command without arguments.
	Used to create constant outputs for reduction.
	"""
	return ['empty']

def unix_compiler_collection(context, output, inputs,
		mechanism=None,
		language=None, # The selected language.
		format=None, # PIC vs PIE vs PDC
		verbose=True, # Enable verbose output.

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
			'size': 's',
		}
	):
	"""
	Construct an argument sequence for a common compiler collection command.

	&unix_compiler_collection is the interface for constructing compilation
	commands for a compiler collection.
	"""
	get = context.get

	fdyna = get('dynamics')
	purpose = get('variants')['purpose']
	sys = get('system')

	command = [None, compile_flag]
	if verbose:
		command.append(verbose_flag)

	# Add language flag if it's a compiler collection.
	if mechanism.get('type') == 'collection':
		if language is not None:
			command.extend((language_flag, language))

	if 'standards' in sys:
		standard = sys['standards'].get(language, None)
		if standard is not None and standard_flag is not None:
			command.append(standard_flag + '=' + standard)

	command.append(visibility) # Encourage use of SYMBOL() define.
	command.append(color)

	# -fPIC, -fPIE or nothing. -mdynamic-no-pic for MacOS X.
	format_flags = format_map.get(format)
	if format_flags is not None:
		command.append(format_flags)

	# Compiler optimization target: -O0, -O1, ..., -Ofast, -Os, -Oz
	co = optimizations[purpose]
	command.append(co_flag + co)

	# Include debugging symbols.
	command.append(debug_flag)

	overflow_spec = get('overflow')
	if overflow_spec is not None:
		command.append(overflow_map[overflow_spec])

	# coverage options for metrics and profile roles.
	if purpose in {'metrics', 'profile'}:
		command.extend(('-fprofile-instr-generate', '-fcoverage-mapping'))

	# Include Directories; -I option.
	sid = list(sys.get('include.directories', ()))
	command.extend([id_flag + str(x) for x in sid])

	command.append(define_flag + 'FAULT_TYPE=' + (fdyna or 'unspecified'))

	# -D defines.
	sp = [define_flag + '='.join(x) for x in sys.get('source.parameters', ())]
	command.extend(sp)

	# -U undefines.
	spo = ['-U' + x for x in sys.get('compiler.preprocessor.undefines', ())]
	command.extend(spo)

	# -include files. Forced inclusion.
	sis = sys.get('include.set') or ()
	for x in sis:
		command.extend((si_flag, x))

	command.extend(sys.get('command.option.injection', ()))

	# finally, the output file and the inputs as the remainder.
	command.extend((output_flag, output))
	command.extend(inputs)

	return command
compiler_collection = unix_compiler_collection

def python_bytecode_compiler(context, output, inputs,
		mechanism=None, format=None, language='python',
		verbose=True, filepath=str):
	"""
	Command constructor for compiling Python bytecode to an arbitrary file.
	"""
	assert language == 'python'
	get = context.get
	purpose = get('variants')['purpose']

	inf, = inputs

	command = [None, filepath(output), filepath(inf), '2' if purpose == 'optimal' else '0']
	return command

def local_bytecode_compiler(context, output, inputs,
		mechanism=None, format=None, language='python',
		verbose=True, filepath=str):
	"""
	Command constructor for compiling Python bytecode to an arbitrary file.
	"""
	assert language == 'python'
	from .bin.pyc import compile_python_bytecode

	get = context.get
	purpose = get('variants')['purpose']

	inf, = inputs

	command = [compile_python_bytecode, filepath(output), filepath(inf), '2' if purpose == 'optimal' else '0']
	return command

def inspect_link_editor(context, output, inputs, mechanism=None, format=None, filepath=str):
	"""
	Command constructor for Mach-O link editor provided on Apple MacOS X systems.
	"""
	get = context.get
	purpose = get('variants')['purpose']
	fdyna = context['dynamics']
	sub = get(context['type'])

	command = [None, fdyna, format]
	command.extend([filepath(x) for x in inputs])
	command.append('--library.directories')
	command.extend([filepath(x) for x in sub.get('library.directories', ())])
	command.append('--library.set')
	command.extend([filepath(x) for x in sub.get('library.set', ())])

	return command

def windows_link_editor(context, output, inputs):
	raise libdev.PendingImplementation("cl.exe linker not implemented")

def macosx_link_editor(context, output, inputs,
		mechanism=None,
		format=None,
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
			'fragment': '-r',
		},
		lto_preserve_exports='-export_dynamic',
		platform_version_flag='-macosx_version_min',
	):
	"""
	Command constructor for Mach-O link editor provided on Apple MacOS X systems.
	"""
	assert context['type'] == 'system'

	get = context.get
	command = [None, '-t', lto_preserve_exports, platform_version_flag, '10.11.0',]

	purpose = get('variants')['purpose']
	sys = get('system')
	fdyna = context['dynamics']

	loutput_type = type_map[fdyna]
	command.append(loutput_type)
	if fdyna == 'executable':
		if format == 'pie':
			command.append(pie_flag)

	if fdyna != 'fragment':
		command.extend([libdir_flag+filepath(x) for x in sys['library.directories']])

		support = mechanism['objects'][fdyna].get(format)
		if support is not None:
			prefix, suffix = support
		else:
			prefix = suffix = ()

		command.extend(prefix)
		command.extend(inputs)

		command.extend([link_flag+filepath(x) for x in sys.get('library.set', ())])
		command.append(link_flag+'System')

		command.extend(suffix)
		if purpose in {'metrics', 'profile'}:
			command.append(mechanism['transformations'][None]['resources']['profile'])

		command.append(mechanism['transformations'][None]['resources']['builtins'])
	else:
		command.extend(inputs)

	command.extend((output_flag, filepath(output)))

	return command

def _r_file_ext(r, ext):
	return r.container / (r.identifier.split('.', 1)[0] + ext)

def web_compiler_collection(context,
		output:libroutes.File,
		inputs:typing.Sequence[libroutes.File],
		**kw
	):
	"""
	Command constructor for emscripten.
	"""
	output = _r_file_ext(output, '.bc')
	return unix_compiler_collection(context, output, inputs, **kw)

def web_link_editor(context,
		output:libroutes.File,
		inputs:typing.Sequence[libroutes.File],

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
	Command constructor for the emcc link editor.

	[Parameters]

	/output
		The file system location to write the linker output to.

	/inputs
		The set of object files to link.

	/verbose
		Enable or disable the verbosity of the command. Defaults to &True.
	"""
	get = context.get
	sys = get('system')
	fdyna = context['dynamics']
	purpose = get('variants')['purpose']

	command = ['emcc']

	# emcc is not terribly brilliant; file extensions are used to determine operation.
	if fdyna == 'fragment':
		suffix = '.bc'
	elif fdyna == 'executable':
		suffix = '.js'
		command.append('--emrun')
	else:
		suffix = '.js'
	output = output.suffix(suffix)

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

def unix_link_editor(context,
		output:libroutes.File,
		inputs:typing.Sequence[libroutes.File],

		mechanism=None,
		format=None,
		verbose=True,

		filepath=str,
		pie_flag='-pie',
		verbose_flag='-v',
		link_flag='-l', libdir_flag='-L',
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
	Command constructor for the unix link editor. For platforms other than &(Darwin) and
	&(Windows), this is the default interface indirectly selected by &.development.bin.configure.

	Traditional link editors have an insane characteristic that forces the user to decide what
	the appropriate order of archives are. The
	(system:command)`lorder` command was apparently built long ago to alleviate this while
	leaving the interface to (system:command)`ld` to be continually unforgiving.

	[Parameters]

	/output
		The file system location to write the linker output to.

	/inputs
		The set of object files to link.

	/verbose
		Enable or disable the verbosity of the command. Defaults to &True.
	"""
	get = context.get
	fdyna = get('dynamics')
	sys = get('system')
	purpose = get('variants')['purpose']

	command = [None]
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

		abi = sys.get('abi')
		if abi is not None:
			command.extend((soname_flag, sys['abi']))

		if allow_runpath:
			# Enable by default, but allow
			add(allow_runpath)

		prefix, suffix = mechanism['objects'][fdyna][format]

		command.extend(prefix)
		command.extend(map(filepath, inputs))
		command.extend(libdirs)
		command.append('-(')
		command.extend(libs)
		command.append('-)')

		if purpose in {'metrics', 'profile'}:
			command.append(mechanism['transformations'][None]['resources']['profile'])

		command.append(mechanism['transformations'][None]['resources']['builtins'])

		command.extend(suffix)
	else:
		# fragment is an incremental link. Most options are irrelevant.
		command.extend(map(filepath, inputs))

	command.extend((output_flag, output))
	return command

if sys.platform == 'darwin':
	link_editor = macosx_link_editor
elif sys.platform in ('win32', 'win64'):
	link_editor = windows_link_editor
else:
	link_editor = unix_link_editor

def rebuild(outputs, inputs):
	"""
	Unconditionally report the &outputs as outdated.
	"""
	return False
reconstruct = rebuild

def updated(outputs, inputs, requirement=None):
	"""
	Return whether or not the &outputs are up-to-date.

	&False returns means that the target should be reconstructed,
	and &True means that the file is up-to-date and needs no processing.
	"""
	olm = None
	for output in outputs:
		if not output.exists():
			# No such object, not updated.
			return False
		lm = output.last_modified()
		olm = min(lm, olm or lm)

	if requirement is not None and olm < requirement:
		# Age requirement not meant, reconstruct.
		return False

	for x in inputs:
		if not x.exists() or x.last_modified() > olm:
			# rebuild if any output is older than any source.
			return False

	# object has already been updated.
	return True

def probe_report(probe, contexts, module):
	"""
	Return the report data of the probe for the given &context.

	This method is called whenever a dependency accesses the report for supporting
	the construction of a target. Probe modules can override this method in
	order to provide parameter sets that depend on the target that is requesting them.
	"""
	global probe_retrieve

	probe_key = getattr(probe, 'key', None)
	if probe_key is not None:
		key = probe_key(probe, contexts, module)
	else:
		key = None

	reports = probe_retrieve(probe, contexts)
	return reports.get(key, {})

def probe_retrieve(probe, contexts=None):
	"""
	Retrieve the stored data collected by the sensor.
	"""
	import pickle
	rf = probe_cache(probe, contexts)
	with rf.open('rb') as f:
		try:
			return pickle.load(f) or {}
		except (FileNotFoundError, EOFError):
			return {}

def probe_record(probe, reports, contexts=None):
	"""
	Record the report for subsequent runs.
	"""
	rf = probe_cache(probe, contexts)
	rf.init('file')

	import pickle
	with rf.open('wb') as f:
		pickle.dump(reports, f)

def probe_cache(probe, contexts=None):
	"""
	Return the route to the probe's recorded report.
	"""
	f = libroutes.File.from_absolute(probe.__cached__)
	last_dot = probe.__name__.rfind('.')
	path = f.container / (probe.__name__[last_dot+1:] + 'pc')
	return path

def factor_defines(module_fullname):
	"""
	Generate a set of defines that describe the factor being created.
	Takes the full module path of the factor as a string.
	"""
	modname = module_fullname.split('.')

	return [
		('FACTOR_QNAME', module_fullname),
		('FACTOR_BASENAME', modname[-1]),
		('FACTOR_PACKAGE', '.'.join(modname[:-1])),
	]

def execution_context_extension_defines(module_fullname, target_fullname):
	"""
	Generate a set of defines for the construction of Python extension modules
	located inside a `extensions` package.

	The distinction from &factor_defines is necessary as there are additional
	defines to manage the actual target. The factor addressing is maintained
	for the `'FACTOR_'` prefixed defines, but `'MODULE_'` specifies the destination
	so that the &.include/fault/python/module.INIT macro can construct the appropriate
	entry point name, and &.include/fault/python/environ.QPATH can generate
	proper paths for type names.
	"""
	mp = module_fullname.rfind('.')
	tp = target_fullname.rfind('.')

	return [
		('FACTOR_QNAME', module_fullname),
		('FACTOR_BASENAME', module_fullname[mp+1:]),
		('FACTOR_PACKAGE', module_fullname[:mp]),

		('MODULE_QNAME', target_fullname),
		('MODULE_PACKAGE', target_fullname[:tp]),
	]

def type_pair(module):
	return (
		module.__factor_type__,
		module.__factor_dynamics__,
	)

def initialize(contexts, module:types.ModuleType, dependents):
	"""
	Initialize the construction context parameters for use by &transform
	and &reduce.

	[ Parameters ]
	/contexts
		The contexts to scan for mechanisms to generate factor processing instructions.
	/module
		The factor to be processed.
	"""
	global merge

	ir = Import.from_fullname(module.__name__)
	work = work_directory(ir)
	wd = libfs.Dictionary.use(work, addressing=fpi_addressing)

	ftype = module.__factor_type__
	fdyna = module.__factor_dynamics__

	# Factor dependencies stated by imports.
	td = list(libfactor.dependencies(module))

	# Find a context that can process the type.
	for x in contexts:
		if ftype in x:
			ctx = x
			mech = x[ftype]
			break
	else:
		raise RuntimeError("context set does not have mechanism for processing " + repr(ftype))

	yield mech

	variants = dict(ctx['variants'])
	mechanisms = ctx

	# Categorize the factor's dependencies.
	index = collections.defaultdict(list)
	for x in td:
		index[type_pair(x)].append(x)

	if ftype == 'system':
		# fault.development.include
		index[('system', 'interfaces')].append(include)

	includes = index[('system', 'interfaces')]
	incdirs = [
		libfactor.sources(Import.from_fullname(x.__name__))
		for x in includes
	]

	# The context parameters for rendering FPI.
	parameters = {
		'variants': variants,
		'irrelevant': set(),
		'key': None,

		'module': module,
		'import': ir,
		'type': ftype,
		'dynamics': fdyna,

		'references': index, # Per-factor_type modules imported by target.

		'suffix': (
			mech['target-file-extensions'].get(fdyna) or \
			mech['target-file-extensions'].get(None) or \
			'.ftr'
		),

		# Context data for system.
		ftype: {
			'type': fdyna,
			'abi': getattr(module, 'abi', None), # -soname for unix/elf.

			'include.directories': incdirs,
			'library.directories': [],
			'library.set': set(),

			'source.parameters': [
				('F_PURPOSE', variants['purpose']),
				('F_PURPOSE_ID', 'F_PURPOSE_' + variants['purpose'].lower()),
			],
		}
	}

	# The code formats and necessary reductions need to be identified.
	# Dependents ultimately determine what this means by designating
	# the type of link that should be used for a given role.

	sys = parameters[ftype]
	sysformats = mech['formats'] # code types used by the object types

	if fdyna not in ('fragment', 'interfaces'):
		# system/user is the dependent.
		# Usually, PIC for extensions, PDC/PIE for executables.
		variants['format'] = sysformats.get(fdyna) or sysformats[None]
	else:
		# For fragments and interfaces, the dependents decide
		# the format set to build. If no format is designated,
		# the default code type and link is configured.

		formats = set()
		links = set()
		for x in dependents:
			formats.add(sysformats[x.__factor_dynamics__])

			dparams = getattr(x, 'parameters', None)
			if dparams is None or not dparams:
				# no configuration to analyze
				continue

			# get any dependency parameters for this target.
			links.add(dparams.get(module))
		# Needs modification for emitting multiple parameter sets.

	if fdyna == 'extension' and libfactor.python_extension(module):
		variants['python_implementation'] = python_triplet

	wk = fpi_work_key(variants)
	parameters['key'] = wk

	sub = ftype[0].upper() + fdyna[0].upper() # Prefix hinting at factor type.
	wd = wd.route(wk, filename=(lambda x: '%s%s'%(sub, str(x))))

	parameters['locations'] = {
		'sources': libfactor.sources(ir, module=module),
		'work': wd, # normally, __pycache__ subdirectory.
		'reduction': wd / 'ftr',

		# Processed Source Directory; becomes ftr if no reduce.
		'output': wd / 'psd',
		'logs': wd / 'log',
		'libraries': wd / 'lib',
	}

	# Full set of regular files in the sources location.
	if '__factor_sources__' in module.__dict__:
		parameters['sources'] = module.__factor_sources__
	else:
		if parameters['locations']['sources'].exists():
			parameters['sources'] = parameters['locations']['sources'].tree()[1]

	# Local dependency set comes first.
	parameters[ftype]['library.directories'] = [parameters['locations']['libraries']]

	libs = index[('system', 'library')]
	fragments = index[('system', 'fragment')]

	libdir = parameters['locations']['libraries']
	for lib in libs:
		libname = identity(lib)
		parameters[ftype]['library.set'].add(libname)

	# Add include directories from libraries and fragments.
	for inc in itertools.chain(libs, fragments):
		ir = Import.from_fullname(inc.__name__)
		incdir = libfactor.sources(ir).container / 'include'
		if incdir.exists():
			sys['include.directories'].append(incdir)

	for probe in index[('system', 'probe')]:
		report = probe_report(probe, contexts, module)
		merge(parameters, report) # probe parameter merge

	from .probes import libpython

	if libpython in index[('system', 'probe')]:
		# Note as building a Python extension.
		ean = libfactor.extension_access_name(module.__name__)
		idefines = execution_context_extension_defines(module.__name__, ean)
	else:
		idefines = factor_defines(module.__name__)

	parameters[ftype]['source.parameters'].extend(idefines)

	if hasattr(module, ftype):
		merge(parameters[ftype], module.system)

	yield parameters

@functools.lru_cache(6)
def context_interface(path):
	"""
	Resolves the construction interface for processing a source or performing
	the final reduction (link-stage).
	"""

	mod, apath = Import.from_attributes(path)
	obj = importlib.import_module(str(mod))
	for x in apath:
		obj = getattr(obj, x)
	return obj

def transform(mechanism, context, filtered=reconstruct):
	"""
	Transform the sources using the mechanisms defined in &context.

	[ Parameters ]
	/context
		The construction context to base the transformation on.
	/type
		The type of transformation to perform.
	"""
	global languages, include

	variants = context['variants']
	ftype = context['type']

	if 'sources' not in context:
		return
	if context['dynamics'] == 'interfaces':
		return

	loc = context['locations']

	emitted = set([loc['output']])
	emitted.add(loc['logs'])
	emitted.add(loc['output'])

	for x in emitted:
		yield ('directory', x)

	mech = mechanism['transformations']
	mech_cache = {}

	commands = []
	for src in context['sources']:
		fnx = src.extension
		if variants['name'] != 'inspect' and fnx in {'h'} or src.identifier.startswith('.'):
			# Ignore header files and dot-files for non-inspect contexts.
			continue

		lang = languages.get(src.extension)

		# Mechanisms support explicit inheritance.
		if lang in mech_cache:
			lmech = mech_cache[lang]
		else:
			if lang in mech:
				lmech = mech[lang]
			else:
				lmech = mech[None]

			layers = [lmech]
			while 'inherit' in lmech:
				basemech = lmech['inherit']
				layers.append(mech[basemech]) # mechanism inheritance
			layers.reverse()
			cmech = {}
			for x in layers:
				merge(cmech, x)

			# cache merged mechanism
			mech_cache[lang] = cmech
			lmech = cmech

		ifpath = lmech['interface'] # python
		xf = context_interface(ifpath)

		#depfile = libroutes.File(loc['dependencies'], src.points)
		depfile = None
		fmt = context['variants']['format']
		obj = libroutes.File(loc['output'], src.points)

		if filtered((obj,), (src,)):
			continue

		logfile = libroutes.File(loc['logs'], src.points)

		for x in (obj, logfile):
			d = x.container
			if d not in emitted:
				emitted.add(d)
				yield ('directory', d)

		genobj = functools.partial(xf, mechanism=lmech, language=lang, format=fmt)

		# compilation
		go = {}
		cmd = genobj(context, obj, (src,))
		method = lmech.get('method')
		if method == 'python':
			cmd[0:1] = (sys.executable, '-m', lmech['command'])
		elif method == 'internal':
			yield ('call', cmd, logfile)
			continue
		else:
			cmd[0] = lmech['command']

		if lmech.get('redirect'):
			yield ('execute-redirection', cmd, logfile, obj)
		else:
			yield ('execute', cmd, logfile)

def reduce(mechanism, context, filtered=reconstruct, sys_platform=sys.platform):
	"""
	Construct the operations for reducing the object files created by &transform
	instructions into a set of targets that can satisfy
	the set of dependents.

	[ Parameters ]
	/context
		The construction context created by &initialize.
	"""

	fmt = context['variants'].get('format')
	if fmt is None:
		return
	if 'reductions' not in mechanism:
		return

	ftype = context['type']
	mech = context[ftype]
	preferred_suffix = context['suffix']
	fdyna = context['dynamics']

	# target library directory containing links to dependencies
	locs = context['locations']
	libdir = locs['libraries']
	ftr = locs['reduction']
	ir = context['import']

	reductions = mechanism['reductions']
	if fdyna in reductions:
		mif = reductions[fdyna]
	else:
		mif = reductions[None]

	xf = context_interface(mif['interface'])

	if 'sources' not in context:
		# Nothing to reduce.
		return

	rr = ftr / (ir.identifier + preferred_suffix)

	yield ('directory', ftr)
	yield ('link', rr, ftr / 'pf.lnk')
	yield ('directory', libdir)

	libs = []

	variants = context['variants']

	for x in context['references'][('system', 'library')]:
		# Create symbolic links inside the target's local library directory.
		# This is done to avoid a large number of -L options in targets
		# with a large number of dependencies.

		# Explicit link of factor.
		xir = Import.from_fullname(x.__name__)
		libdep = reduction(xir, variants)
		li = identity(x)
		lib = libdir / library_filename(sys_platform, li)

		yield ('link', libdep, lib)
		libs.append(li)

	fragments = [
		reduction(Import.from_fullname(x.__name__), variants)
		for x in context['references'][('system', 'fragment')]
	]

	# Discover the known sources in order to identify which objects should be selected.
	fdyna = context['dynamics']

	objdir = locs['output']
	objects = [
		libroutes.File(objdir, x.points) for x in context['sources']
		if x.extension not in {'h'} and not x.identifier.startswith('.')
	]
	if fragments:
		objects.extend([x / fmt for x in fragments])

	if not filtered((rr,), objects):
		# Mechanisms with a configured root means that the
		# transformed objects are referenced by the root file.
		root = mif.get('root')
		if root is not None:
			objects = [objdir / root]

		cmd = xf(context, rr, objects, mechanism=mechanism, format=fmt)
		if mif.get('method') == 'python':
			cmd[0:1] = (sys.executable, '-m', mif['command'])
		else:
			cmd[0] = mif['command']

		if mif.get('redirect'):
			yield ('execute-redirection', cmd, locs['logs'] / 'Reduction', rr)
		else:
			yield ('execute', cmd, locs['logs'] / 'Reduction')

def parse_make_dependencies(make_rule_str):
	"""
	Convert the string suited for Makefiles into a Python list of &str instances.

	! WARNING:
		This implementation currently does not properly accommodate for escapes.
	"""
	files = itertools.chain.from_iterable([
		x.split() for x in make_rule_str.split(' \\\n')
	])
	next(files); next(files) # ignore the target rule portion and the self pointer.
	return list(files)

class Construction(libio.Processor):
	"""
	Construction process manager. Maintains the set of target modules to construct and
	dispatches the work to be performed for completion in the appropriate order.

	! TODO:
		- Rewrite as a Flow.
		- Generalize; flow accepts jobs and emits FlowControl events
			describing the process. (rusage, memory, etc of process)

	! DEVELOPER:
		Primarily, this class traverses the directed graph constructed by imports
		performed by the target modules being built.

		Refactoring could yield improvements; notably moving the work through a Flow
		in order to leverage obstruction signalling.
	"""

	def __init__(self,
			contexts, modules,
			requirement=None,
			reconstruct=False,
			processors=4
		):
		self.reconstruct = reconstruct
		self.failures = 0

		self.contexts = contexts # series of context resources for supporting subjects
		self.modules = modules

		# Manages the dependency order.
		self.sequence = sequence([x[1] for x in modules])

		self.tracking = collections.defaultdict(list) # module -> sequence of sets of tasks
		self.progress = collections.Counter()

		self.process_count = 0 # Track available subprocess slots.
		self.process_limit = processors
		self.command_queue = collections.deque()

		self.continued = False
		self.activity = set()
		self.requirement = requirement # outputs must be newer.

		super().__init__()

	def actuate(self):
		if self.reconstruct:
			self._filter = reconstruct
		else:
			self._filter = functools.partial(updated, requirement=self.requirement)

		try:
			modules, deps = next(self.sequence) # WorkingSet
		except StopIteration:
			# Done in actuation? Empty set.
			self.terminate()
			return

		for x in modules:
			self.collect(x, deps.get(x, ()))

		self.drain_process_queue()
		return super().actuate()

	def collect(self, module, dependents=()):
		"""
		Collect all the work to be done for building the desired targets.
		"""
		tracks = self.tracking[module]

		if type_pair(module) == ('system', 'probe'):
			# Needs to be transformed into a job.
			# Probes are deployed per dependency.
			probe_set = [('probe', module, x) for x in dependents]
			tracks.append(probe_set)
		else:
			mech, *sets = initialize(self.contexts, module, dependents)

			for ctx in sets:
				if 'reductions' not in mech:
					# For mechanisms that do not specify reductions,
					# the transformed set is the factor.
					# XXX: Incomplete; check if specific output is absent.
					ctx['locations']['output'] = ctx['locations']['reduction']

				xf = list(transform(mech, ctx, filtered=self._filter))

				# If any commands or calls are made by the transformation,
				# reconstruct the target.
				for x in xf:
					if x[0] not in ('directory', 'link'):
						f = reconstruct
						break
				else:
					f = self._filter

				rd = list(reduce(mech, ctx, filtered=f))
				tracks.extend((xf, rd))

		if tracks:
			self.progress[module] = -1
			self.dispatch(module)
		else:
			self.activity.add(module)

			if self.continued is False:
				# Consolidate loading of the next set of processors.
				self.continued = True
				self.ctx_enqueue_task(self.continuation)

	def probe_execute(self, module, instruction):
		assert instruction[0] == 'probe'

		sector = self.sector
		dep = instruction[2]

		if getattr(module, 'key', None) is not None:
			key = module.key(module, self.contexts, dep)
		else:
			key = None

		reports = probe_retrieve(module, self.contexts)

		if key in reports:
			# Needed report is cached.
			self.progress[module] += 1
		else:
			f = lambda x: self.probe_dispatch(module, self.contexts, dep, key, x)
			t = libio.Thread(f)
			self.sector.dispatch(t)

	def probe_dispatch(self, module, contexts, dep, key, tproc):
		# Executed in thread.
		sector = self.controller # Allow libio.context()

		report = module.deploy(module, contexts, dep)
		self.ctx_enqueue_task(
			functools.partial(
				self.probe_exit,
				tproc,
				contexts=contexts,
				module=module,
				report=report,
				key=key
			),
		)

	def probe_exit(self, processor, contexts=None, module=None, report=None, key=None):
		self.progress[module] += 1
		self.activity.add(module)

		reports = probe_retrieve(module, contexts)
		reports[key] = report
		probe_record(module, reports, contexts)

		if self.continued is False:
			# Consolidate loading of the next set of processors.
			self.continued = True
			self.ctx_enqueue_task(self.continuation)

	def process_execute(self, instruction):
		module, ins = instruction
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
		sp.atexit(functools.partial(self.process_exit, start=libtime.now(), descriptor=(typ, cmd, log), module=module))

	def process_exit(self, processor, start=None, module=None, descriptor=None):
		assert module is not None
		assert descriptor is not None
		self.progress[module] += 1
		self.process_count -= 1
		self.activity.add(module)

		typ, cmd, log = descriptor
		pid, status = processor.only
		exit_method, exit_code, core_produced = status
		if exit_code != 0:
			self.failures += 1

		l = ''
		l += ('\n[Profile]\n')
		l += ('/factor\n\t%s\n' %(module.__name__,))

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
		After process slots have been cleared by &process_exit,
		&continuation is called and performs this method to execute
		system processes enqueued in &command_queue.
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
		Process exits occurred that may trigger an addition to the working set of tasks.
		Usually called indirectly by &process_exit, this manages the collection
		of further work identified by the sequenced dependency tree managed by &sequence.
		"""
		# Reset continuation
		self.continued = False
		modules = list(self.activity)
		self.activity.clear()

		completions = set()

		for x in modules:
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

	def dispatch(self, module):
		"""
		Process the collected work for the module.
		"""
		assert self.progress[module] == -1
		self.progress[module] = 0

		for x in self.tracking[module][0]:
			if x[0] in ('execute', 'execute-redirection'):
				self.command_queue.append((module, x))
			elif x[0] == 'directory':
				for y in x[1:]:
					y.init('directory')
				self.progress[module] += 1
			elif x[0] == 'link':
				cmd, src, dst = x
				dst.link(src)
				self.progress[module] += 1
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
				self.progress[module] += 1
			elif x[0] == 'probe':
				self.probe_execute(module, x)
			else:
				print('unknown instruction', x)

		if self.progress[module] >= len(self.tracking[module][0]):
			self.activity.add(module)

			if self.continued is False:
				self.continued = True
				self.ctx_enqueue_task(self.continuation)

	def finish(self, modules):
		try:
			for x in modules:
				del self.progress[x]
				del self.tracking[x]

			new, deps = self.sequence.send(modules)
			for x in new:
				self.collect(x, deps.get(x, ()))
		except StopIteration:
			self.terminate()

	def terminate(self, by=None):
		# Manages the dispatching of processes,
		# so termination is immediate.
		self.terminating = False
		self.terminated = True
		self.controller.exited(self)
