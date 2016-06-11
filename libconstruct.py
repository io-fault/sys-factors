"""
Management of target construction jobs for creating system [context] executable,
libraries, and extensions.

The effects that &.libconstruct causes are heavily influenced by the Construction Context.
The Construction Context is defined as a set of roles which ultimately determine the
necessary procedures for constructing a target.

[ Properties ]

/roles
	Dictionary of construction roles used by libconstruct to manage different
	transformations of &libdev.Sources modules.

/library_extensions
	Used by &library_filename to select the appropriate extension
	for `system.library` and `system.extension` factors.

/python_triplet
	The `-` separated strings representing the currently executing Python context.
	Used to construct directories for Python extension builds.
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

from . import libfactor
from . import include
from . import library as libdev
from .probes import libpython # Used to detect Python Extensions.

from ..chronometry import library as libtime
from ..io import library as libio
from ..system import library as libsys
from ..routes import library as libroutes

from ..xml import library as libxml
from ..xml import lxml

roles = {
	'optimal': 'Maximum optimizations with debugging symbols separated or stripped',

	'debug': 'Reduced optimizations and defines for debugging',
	'test': 'Debug role with minor optimizations and support for injections',
	'profile': 'Raw profiling for custom collections',
	'coverage': 'Raw coverage for custom collections',

	'metrics': 'Test role with profiling and coverage collection enabled',

	'introspection':
		'Role for structuring coefficients (sources) into a form used by documentation tools',
	'core': 'The role used to represent the conceptual base of other roles.',
}

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

# Used as the context name for extension modules.
python_triplet = libdev.python_context(
	sys.implementation.name, sys.version_info, sys.abiflags, sys.platform
)

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
	Merge the given &source into &self applying merge operations
	defined for keys or the classes of the destinations' keys.
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
	'lc': 'https://fault.io/xml/libconstruct',
	'd': 'https://fault.io/xml/data',
}

def root_context_directory(env='FAULT_LIBCONSTRUCT'):
	"""
	Return the &libroutes.File instance to the root context.
	By default, this is (fs:path)`~/.fault/libconstruct`, but can
	be overridden by the (environ)`FAULT_LIBCONSTRUCT` variable.

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

	return libroutes.File.home() / '.fault' / 'libconstruct'

def root_context(directory, selection, role):
	xf = directory / (selection or 'host') / (role + '.xml')
	if not xf.exists():
		return None, {}

	with xf.open() as f:
		xml = lxml.etree.parse(f)

	d = xml.xpath('/lc:libconstruct/lc:context/d:*', namespaces=xml_namespaces)[0]
	data = libxml.Data.structure(d)
	return xml, data

def compile_bytecode(target, source):
	global importlib
	pyc_cache = importlib.util.cache_from_source(source)

# Specifically for identifying files to be compiled and how.
extensions = {
	'c': ('c',),
	'c++': ('c++', 'cxx', 'cpp'),
	'objective-c': ('m',),
	'ada': ('ads', 'ada'),
	'assembly': ('asm',),
	'bitcode': ('bc',), # clang

	'haskell': ('hs', 'hsc'),
}

languages = {}
for k, v in extensions.items():
	for y in v:
		languages[y] = k

def mount(role, route, target, ext_suffixes=importlib.machinery.EXTENSION_SUFFIXES):
	"""
	Mount an execution context extension module so that the constructed binary can be
	used by the context (Python).

	After extension modules have been constructed, they may not be available for use.
	The &mount function performs the necessary filesystem modifications in order expose
	the extension modules for use.
	"""
	# system.extension being built for this Python
	# construct links to optimal.
	# ece's use a special context derived from the Python install
	# usually consistent with the triplet of the first ext suffix.
	global python_triplet

	outfile = target.output(context=python_triplet, role=role)

	# peel until it's outside the first extensions directory.
	pkg = route
	while pkg.identifier != 'extensions':
		pkg = pkg.container
	names = route.absolute[len(pkg.absolute):]
	pkg = pkg.container

	link_target = pkg.file().container.extend(names)
	for suf in ext_suffixes + ['.pyd', '.dylib']:
		rmf = link_target.suffix(suf)
		if rmf.exists():
			print('removing', str(rmf))
			rmf.void()

	dsym = link_target.suffix('.so.dSYM')
	if dsym.exists():
		print('removing', str(dsym))
		dsym.void()

	link_target = link_target.suffix(ext_suffixes[0])
	print('linking', outfile, '->', link_target)
	link_target.link(outfile, relative=True)

def collect(module, types=(libfactor.SystemModule, libfactor.ProbeModule)):
	"""
	Return the set of dependencies that the given module has.
	"""
	for v in module.__dict__.values():
		if isinstance(v, types):
			yield v

def traverse(working, tree, inverse, module):
	"""
	Invert the directed graph of dependencies from the target modules.

	System object factor modules import their dependencies into their global
	dictionary forming a directed graph. The imported system object factor
	modules are identified as dependencies that need to manifested in order
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

		for module in completion:
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
	if module.system_object_type == 'library':
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

def unix_compiler_collection(context, output, inputs,
		mechanism=None,
		language=None, # The selected language.
		format=None, # PIC vs PIE vs PDC
		verbose=True, # Enable verbose output.
		emit_dependencies=False,

		verbose_flag='-v',
		language_flag='-x', standard_flag='-std',
		emit_dependencies_flag='-M',
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
			'metrics': '1',
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
	sys = get('system')
	typ = sys.get('type')
	role = get('role')
	command = [None, compile_flag]
	if verbose:
		command.append(verbose_flag)

	# Add language flag if it's a compiler collection.
	if mechanism['type'] == 'collection':
		if language is not None:
			command.extend((language_flag, language))

	if 'standards' in context:
		standard = get('standards', None).get(format, None)
		if standard is not None and standard_flag is not None:
			command.append(standard_flag + '=' + standard)

	command.append(visibility) # Encourage use of SYMBOL() define.
	command.append(color)

	# -fPIC, -fPIE or nothing. -mdynamic-no-pic for MacOS X.
	format_flags = format_map.get(format)
	if format_flags is not None:
		command.append(format_flags)

	# Compiler optimization target: -O0, -O1, ..., -Ofast, -Os, -Oz
	co = optimizations[role]
	command.append(co_flag + co)

	# Include debugging symbols.
	command.append(debug_flag)

	overflow_spec = get('overflow')
	if overflow_spec is not None:
		command.append(overflow_map[overflow_spec])

	# coverage options for metrics and profile roles.
	coverage = get('coverage', False)
	if role in {'metrics', 'profile'}:
		command.extend(('-fprofile-instr-generate', '-fcoverage-mapping'))

	# Include Directories; -I option.
	sid = list(sys.get('include.directories', ()))
	command.extend([id_flag + str(x) for x in sid])

	# -include files. Forced inclusion.
	sis = sys.get('include.set') or ()
	for x in sis:
		command.extend((si_flag, x))

	module = get('module')

	# -D defines.
	sp = [define_flag + '='.join(x) for x in sys.get('source.parameters', ())]
	command.extend(sp)

	command.append(define_flag + 'FAULT_TYPE=' + (typ or 'unspecified'))

	# -U undefines.
	spo = ['-U' + x for x in sys.get('compiler.preprocessor.undefines', ())]
	command.extend(spo)

	if emit_dependencies:
		command.append(emit_dependencies_flag)
		for k, v, default in dependency_options:
			setting = get(k)
			if setting or setting is None and default:
				command.append(v)

	command.extend(get('command.option.injection', ()))

	# finally, the output file and the inputs as the remainder.
	command.extend((output_flag, output))
	command.extend(inputs)

	return command
compiler_collection = unix_compiler_collection

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
		ref_flags = {
			'weak': '-weak-l',
			'lazy': '-lazy-l',
			'default': '-l',
		},
		type_map = {
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
	get = context.get
	command = [None, '-t', lto_preserve_exports, platform_version_flag, '10.11.0',]

	sys = get('system')
	typ = sys.get('type')

	loutput_type = type_map[typ]
	command.append(loutput_type)
	if typ == 'executable':
		if format == 'pie':
			command.append(pie_flag)

	if typ != 'fragment':
		command.extend([libdir_flag+filepath(x) for x in sys['library.directories']])

		support = context['mechanisms']['system']['objects'][typ].get(format)
		if support is not None:
			prefix, suffix = support
		else:
			prefix = suffix = ()

		command.extend(prefix)
		command.extend(inputs)

		command.extend([link_flag+filepath(x) for x in sys.get('library.set', ())])
		command.append(link_flag+'System')

		command.extend(suffix)
	else:
		command.extend(inputs)

	command.extend((output_flag, filepath(output)))

	return command

def unix_link_editor(context, output, inputs,
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

		use_static='-Bstatic',
		use_shared='-Bdynamic',
	):
	"""
	Command constructor for the unix link editors.

	GNU ld has an insane characteristic that forces the user to decide what
	the appropriate order of archives are. The
	(system:command[posix])`lorder` was apparently built long ago to alleviate this while
	leaving the interface to (system:command[posix])`ld` to be continually unforgiving.

	[Parameters]

	/filepath
		Override to adjust the selected path. File paths passed are &libroutes.File
		instances that are absolute paths. In cases where scripts are being generated,
		the path may need modification in order to represented in a portable fashion.

	/verbose
		Enable or disable the verbosity of the command. Defaults to &True.
	"""
	get = context.get
	sys = get('system')
	typ = sys.get('type')

	command = [None]
	add = command.append
	iadd = command.extend

	if verbose:
		add(verbose_flag)

	loutput_type = type_map[typ] # failure indicates bad type parameter to libfactor.load()
	if loutput_type:
		add(loutput_type)

	if typ != 'fragment':
		sld = sys.get('library.directories', ())
		libdirs = [libdir_flag + filepath(x) for x in sld]

		sls = sys.get('library.set', ())
		libs = [link_flag + filepath(x) for x in sls]
		if 'abi' in sys:
			command.extend((soname_flag, sys['abi']))

		rt = context['mechanisms']['system']['objects'][typ][format]
		prefix, suffix = rt

		command.extend(prefix)
		command.extend(map(filepath, inputs))
		command.extend(libdirs)
		command.extend(libs)
		command.extend(suffix)
	else:
		command.extend(map(filepath, inputs))

	command.extend((output_flag, output))
	return command

if sys.platform == 'darwin':
	link_editor = macosx_link_editor
elif sys.platform in ('win32', 'win64'):
	link_editor = windows_link_editor
else:
	link_editor = unix_link_editor

def updated(outputs, inputs, depfile):
	"""
	Return whether or not the &outputs need to be updated.
	"""
	olm = None
	for x in outputs:
		if not x.exists():
			# No such object, not updated.
			return False
		lm = x.last_modified()
		olm = min(lm, olm or lm)

	for x in inputs:
		if olm < x.last_modified():
			# rebuild if any output is older than any source.
			return False

	if depfile is not None and depfile.exists():
		# Alter to only pay attention to project and context files.

		# check identified dependencies if any
		with depfile.open('r') as f:
			pmd = parse_make_dependencies(f.read())
			deps = list(map(libroutes.File.from_absolute, pmd))

		for dep in deps:
			if olm < dep.last_modified():
				return False

	# object has already been updated.
	return True

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

@functools.lru_cache(8)
def mechanism(directory, context, role):
	"""
	Get the mechanism from the libconstruct directory for the given role.

	This extracts the data from the XML files often generated by &.bin.configure.
	The mechanism is the merger of the core root context and the role; where the role's
	data is merged on top of core.
	"""
	global merge, root_context

	core_doc, core_data = root_context(directory, context, 'core')
	role_doc, role_data = root_context(directory, context, role)
	merge(core_data, role_data)

	return core_data

def initialize(
		selection:str, context:str, role:str,
		module:libdev.Sources, dependents,
		lcd=None
	):
	"""
	Initialize a construction context for use by &transform and &reduce.

	Given a &context name and a &role, initialize a construction context for producing the
	target of the given &module.

	[ Parameters ]
	/lcd
		Optional directory path overriding the environment variable or the default home
		path. Normally unused.
	"""
	global merge

	# Factor dependencies stated by imports.
	td = list(module.dependencies())

	# Categorize the module's dependencies.
	incdirs = [include.directory]
	probes = []
	libs = []
	fragments = []
	refs = []
	for x in td:
		if isinstance(x, libfactor.IncludesModule):
			incdirs.append(x.sources)
		elif isinstance(x, libfactor.ProbeModule):
			probes.append(x)
		elif isinstance(x, libfactor.SystemModule):
			if x.system_object_type == 'library':
				libs.append(x)
			elif x.system_object_type == 'fragment':
				fragments.append(x)
		else:
			refs.append(x)

	work = libfactor.cache_directory(module, context, role, 'x').container

	# context: context -> role -> purpose -> format
	mechanisms = mechanism(lcd or root_context_directory(), selection, role)

	# the full context dictionary.
	parameters = {
		'name': context, # context name
		'module': module,
		'role': role,

		'probes': probes, # libfactor.ProbeModule
		'references': refs, # libdev.Sources instances

		'locations': {
			'sources': module.sources,
			'work': work,
			'output': libfactor.cache_directory(module, context, role, 'out'),
			'logs': libfactor.cache_directory(module, context, role, 'log'),
			'libraries': libfactor.cache_directory(module, context, role, 'lib'),
			'dependencies': libfactor.cache_directory(module, context, role, 'dl'),
		},

		# Mechanisms (compiler/linker) for the context+role combination.
		'mechanisms': mechanisms,

		# Context data for system subject.
		'system': {
			'type': getattr(module, 'system_object_type', None), # Conceptual
			'abi': getattr(module, 'abi', None), # -soname for unix/elf.
			'formats': set(),
			'libraries': libs, # dependencies that are system libraries.
			'fragments': fragments,
			'include.directories': incdirs,

			'library.directories': [],
			'library.set': set(),

			'source.parameters': [
				('F_ROLE', role),
				('F_ROLE_ID', 'F_ROLE_' + role.upper() + '_ID'),
			],
		}
	}

	# The code formats and necessary reductions need to be identified.
	# Dependents ultimately determine what this means by designating
	# the type of link that should be used for a given role.

	sys = parameters['system']
	typ = sys['type']
	sysformats = mechanisms['system']['formats'] # code types used by the object types

	if typ in {'executable', 'extension', 'library'}:
		# system/user is the dependent.
		# Usually, PIC for extensions, PDF for executables.
		sys['formats'].add(sysformats[typ])
	else:
		# For fragments, the dependents decide
		# the format set to build. If no format is designated,
		# the default code type and link is configured.

		links = set()
		for x in dependents:
			sys['formats'].add(sysformats[x.system_object_type])

			dparams = getattr(x, 'parameters', None)
			if dparams is None or not dparams:
				# no configuration to analyze
				continue

			# get any dependency parameters for this target.
			links.add(dparams.get(module))

	# Full set of regular files in the sources location.
	if parameters['locations']['sources'].exists():
		parameters['sources'] = parameters['locations']['sources'].tree()[1]

	# Local dependency set comes first.
	parameters['system']['library.directories'] = [parameters['locations']['libraries']]

	libdir = parameters['locations']['libraries']
	for lib in libs:
		libname = identity(lib)
		parameters['system']['library.set'].add(libname)

	# Add include directories from libraries and fragments.
	for inc in itertools.chain(libs, fragments):
		incdir = inc.sources.container / 'include'
		if incdir.exists():
			sys['include.directories'].append(incdir)

	for probe in probes:
		report = probe.report(probe, selection or 'host', role, module)
		merge(parameters, report) # probe parameter merge

	if libpython in probes:
		# Note as building a Python extension.
		parameters['execution_context_extension'] = True
		men = parameters['mount_point'] = module.extension_name()
		idefines = execution_context_extension_defines(module.__name__, men)
	else:
		parameters['execution_context_extension'] = False
		idefines = factor_defines(module.__name__)

	parameters['system']['source.parameters'].extend(idefines)

	return parameters

@functools.lru_cache(6)
def context_interface(path):
	"""
	Resolves the construction interface for processing a source or performing
	the final reduction (link-stage).
	"""
	mod, apath = libroutes.Import.from_attributes(path)
	obj = importlib.import_module(str(mod))
	for x in apath:
		obj = getattr(obj, x)
	return obj

def transform(context, filtered=(lambda x,y,z: False)):
	"""
	Transform the sources using the mechanisms defined in &context.

	[ Parameters ]
	/context
		The construction context to base the transformation on.
	/type
		The type of transformation to perform.
	"""
	global languages, include

	if 'sources' not in context:
		return

	sys = context['system']
	loc = context['locations']
	formats = sys['formats']

	emitted = set([loc['output']])
	emitted.add(loc['logs'])
	emitted.add(loc['output'])
	emitted.update([loc['output'] / typ for typ in formats])

	for x in emitted:
		yield ('directory', x)

	mech = context['mechanisms']
	mech = mech['system']['transformations']
	mech_cache = {}

	commands = []
	for src in context['sources']:
		fnx = src.extension
		if fnx in {'h'} or src.identifier.startswith('.'):
			# Ignore header files and dot-files.
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

		depfile = libroutes.File(loc['dependencies'], src.points)
		for fmt in formats:
			# Iterate over formats (pic, pdc, pie).
			obj = libroutes.File(loc['output'] / fmt, src.points)

			if filtered((obj,), (src,), depfile):
				continue

			logfile = libroutes.File(loc['logs'] / fmt, src.points)

			for x in (obj, depfile, logfile):
				d = x.container
				if d not in emitted:
					emitted.add(d)
					yield ('directory', d)

			genobj = functools.partial(xf, mechanism=lmech, language=lang, format=fmt)

			# compilation
			go = {}
			compilation = genobj(context, obj, (src,))
			compilation[0] = lmech['command']

			yield ('execute', compilation, logfile)

def reduce(context, filtered=(lambda x,y,z: False), sys_platform=sys.platform):
	"""
	Construct the operations for reducing the object files created by &transform
	instructions into a set of targets that can satisfy
	the set of dependents.

	[ Parameters ]
	/context
		The construction context created by &initialize.
	"""

	ctx = context['name']
	role = context['role']
	# target library directory containing links to dependencies
	locs = context['locations']
	libdir = locs['libraries']

	subject = context.get('subject', 'system')
	mech = context['mechanisms'][subject]['reductions'][None]
	xf = context_interface(mech['interface'])

	sys = context['system']
	formats = tuple(sys['formats'])

	if 'sources' not in context:
		# Nothing to reduce.
		return

	yield ('directory', libdir)

	libs = []

	for x in context['system']['libraries']:
		# Create symbolic links inside the target's local library directory.
		# This is done to avoid a large number of -L options in targets
		# with a large number of dependencies.

		# Explicit link of factor.
		libdep = x.output(ctx, role)
		li = identity(x)
		lib = libdir / library_filename(sys_platform, li)
		yield ('link', libdep, lib)
		libs.append(li)

	fragments = [x.output(ctx, role) for x in context['system']['fragments']]

	# Discover the known sources in order to identify which objects should be selected.
	output_base = context['module'].output(ctx, role)
	typ = sys['type']
	if typ == 'fragment':
		# Fragments may have multiple builds.
		# A library may want PIC and an executable, PIE.
		# The additional compilation allows the fragment to offer
		# library or executable specific code as well.
		outputs = [
			output_base / fmt for fmt in formats
		]
		yield ('directory', output_base)
	else:
		assert len(formats) == 1
		outputs = (output_base,)

	for fmt, output in zip(formats, outputs):
		objdir = locs['output'] / fmt
		objects = [
			libroutes.File(objdir, x.points) for x in context['sources']
			if x.extension not in {'h'} and not x.identifier.startswith('.')
		]
		if fragments:
			objects.extend([x / fmt for x in fragments])

		if not filtered((output,), objects, None):
			cmd = xf(context, output, objects, mechanism=mech, format=fmt)
			cmd[0] = mech['command']

			yield ('execute', cmd, locs['logs'] / fmt / 'reduction')

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

	! DEVELOPER:
		Primarily, this class traverses the directed graph constructed by imports
		performed by the target modules being built.

		Refactoring could yield improvements; notably moving the work through a Flow
		in order to leverage obstruction signalling.
	"""

	def __init__(self, context, role, modules, processors=4):
		self.failures = 0
		self.cx_context = context
		self.cx_role = role
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
		super().__init__()

	def actuate(self):
		try:
			modules, deps = next(self.sequence) # WorkingSet
		except StopIteration:
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
		context = self.cx_context # [construction] context name
		tracks = self.tracking[module]

		if context is None:
			# context was not selected, so default to the host
			# context. In cases of Python extension, this is the triplet.
			if getattr(module, 'execution_context_extension', False):
				context = python_triplet
			else:
				# Default 'host' context.
				context = 'host'
		else:
			# context was explicitly stated meaning
			# extension modules are not built for mounting.
			pass

		if isinstance(module, libfactor.ProbeModule):
			# Needs to be transformed into a job.
			# Probes are deployed per dependency.
			probe_set = [('probe', module, x) for x in dependents]
			tracks.append(probe_set)
		else:
			ctx = initialize(
				self.cx_context, context, self.cx_role, module, dependents
			)
			xf = list(transform(ctx, filtered=updated))
			rd = list(reduce(ctx, filtered=updated))
			tracks.extend((xf, rd))

		if tracks:
			self.progress[module] = -1
			self.dispatch(module)
		else:
			self.activity.add(module)

			if self.continued is False:
				# Consolidate loading of the next set of processors.
				self.continued = True
				self.fio_enqueue(self.continuation)

	def probe_execute(self, module, instruction):
		assert instruction[0] == 'probe'

		sector = self.sector
		dep = instruction[2]
		ctx = self.cx_context or 'host'
		role = self.cx_role

		key = module.key(module, ctx, role, dep)
		reports = module.retrieve(ctx, role)

		if key in reports:
			# Needed report is cached.
			self.progress[module] += 1
		else:
			deploy = module.deploy
			xreport = module.deploy(module, ctx, role, dep)
			if isinstance(xreport, types.CoroutineType):
				# wait for completion
				cop = libio.Coroutine(xreport)
				self.sector.dispatch(cop)
				cop.atexit(functools.partial(self.probe_complete,
						module=module,
						reports=reports,
						key=key
					),
				)
			else:
				reports[key] = xreport
				if xreport is not None:
					# &None indicates constant probe; &report will build on demand.
					module.record(reports, ctx, role)

				self.progress[module] += 1

	def probe_exit(self, processor, module=None, reports=None, key=None):
		self.progress[module] += 1
		self.activity.add(module)

		try:
			report = processor.product
			reports[key] = report
			module.record(reports, ctx, role)
		finally:
			pass

		if self.continued is False:
			# Consolidate loading of the next set of processors.
			self.continued = True
			self.fio_enqueue(self.continuation)

	def process_execute(self, instruction):
		module, (typ, cmd, log) = instruction
		assert typ == 'execute'
		strcmd = tuple(map(str, cmd))

		pid = None
		with log.open('wb') as f:
			f.write(b'[Command]\n')
			f.write(' '.join(strcmd).encode('utf-8'))
			f.write(b'\n\n[Standard Error]\n')

			ki = libsys.KInvocation(str(cmd[0]), strcmd)
			with open('/dev/null', 'rb') as ci, open('/dev/null', 'wb') as co:
				pid = ki(fdmap=((ci.fileno(), 0), (co.fileno(),1), (f.fileno(),2)))
				sp = libio.Subprocess(pid)

		#print(' '.join(strcmd) + ' #' + str(pid))
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

		with log.open('a') as f:
			f.write('\n[Profile]\n')
			f.write('/factor\n\t%s\n' %(module.__name__,))

			if log.points[-1] != 'reduction':
				f.write('/subject\n\t%s\n' %('/'.join(log.points),))
			else:
				f.write('/subject\n\treduction\n')

			f.write('/pid\n\t%d\n' %(pid,))
			f.write('/status\n\t%s\n' %(str(status),))
			f.write('/start\n\t%s\n' %(start.select('iso'),))
			f.write('/stop\n\t%s\n' %(libtime.now().select('iso'),))

		if self.continued is False:
			# Consolidate loading of the next set of processors.
			self.continued = True
			self.fio_enqueue(self.continuation)

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
			if x[0] == 'execute':
				self.command_queue.append((module, x))
			elif x[0] == 'directory':
				for y in x[1:]:
					y.init('directory')
				self.progress[module] += 1
			elif x[0] == 'link':
				cmd, src, dst = x
				dst.link(src)
				self.progress[module] += 1
			elif x[0] == 'probe':
				self.probe_execute(module, x)
			else:
				print('unknown instruction', x)

		if self.progress[module] >= len(self.tracking[module][0]):
			self.activity.add(module)

			if self.continued is False:
				self.continued = True
				self.fio_enqueue(self.continuation)

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
