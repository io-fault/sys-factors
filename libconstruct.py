"""
Management of target construction jobs for creating system [context] executable,
libraries, and extensions.

[ Properties ]

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
import builtins
import subprocess
import functools
import itertools
import collections
import contextlib
import importlib
import importlib.machinery

from . import libfactor
from . import include
from . import library as libdev
from .probes import libpython

from ..chronometry import library as libtime
from ..io import library as libio
from ..system import library as libsys
from ..routes import library as libroutes

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
	dict: dict.update,
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
			if key in operations:
				# merge operation overloaded by key
				mokey = key
			else:
				# merge parameters by class
				mokey = parameters[key].__class__

			merge_op = operations[mokey]

			# DEFECT: The manipulation methods often return None.
			r = merge_op(parameters[key], source[key])
			if r is not parameters[key] and r is not None:
				parameters[key] = r
		else:
			parameters[key] = source[key]

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

data_fields = [
	'ignored', # relative source paths that are not processed.
	'language', # the set of languages with configuration
	'libraries', # the set of libraries to link against (usually dynamic)
]

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
	Construct an inverted directed graph of dependencies from the
	module's dependencies.

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

def unix_compiler_collection(context, output, inputs,
		collection=True, # Assume the command is a compiler collection.
		verbose=True, # Enable verbose output.
		language=None, # The selected language.
		emit_dependencies=False,

		verbose_flag='-v',
		language_flag='-x', standard_flag='-std',
		emit_dependencies_flag='-M',
		visibility='-fvisibility=hidden',

		output_flag='-o',
		compile_flag='-c',
		sid_flag='-isystem',
		id_flag='-I', si_flag='-include',
		debug_flag='-g',
		pic_flag='-fPIC',
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
			'survey': '1',
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
	role = get('role')
	command = [get('compiler', '/x/realm/bin/clang'), compile_flag]
	if verbose:
		command.append(verbose_flag)

	if collection:
		if language is not None:
			command.extend((language_flag, language))

	if 'standards' in context:
		standard = get('standards', None).get(language, None)
		if standard is not None and standard_flag is not None:
			command.append(standard_flag + '=' + standard)

	command.append(visibility) # Encourage use of SYMBOL() define.

	# -fPIC or not.
	link_type = get('type', 'dynamic')
	if link_type == 'dynamic':
		command.append(pic_flag)

	# Compiler optimization target: -O0, -O1, ..., -Ofast, -Os, -Oz
	co = optimizations[role]
	command.append(co_flag + co)

	# Include debugging symbols.
	command.append(debug_flag)

	overflow_spec = get('overflow')
	if overflow_spec is not None:
		command.append(overflow_map[overflow_spec])

	# coverage options for survey and profile roles.
	coverage = get('coverage', False)
	if role in {'survey', 'profile'}:
		command.extend(('-fprofile-instr-generate', '-fcoverage-mapping'))

	# Include Directories; -I option.
	sid = list(get('system.include.directories', ()))
	command.extend([id_flag + str(x) for x in sid])

	# -include files. Forced inclusion.
	sis = get('include.set') or ()
	for x in sis:
		command.extend((si_flag, x))

	module = get('module')

	# -D defines.
	sp = [define_flag + '='.join(x) for x in get('compiler.preprocessor.defines', ())]
	command.extend(sp)

	# -U undefines.
	spo = ['-U' + x for x in get('compiler.preprocessor.undefines', ())]
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
	pass

def macosx_link_editor(context, output, inputs,
		filepath=str,
		link_flag='-l', libdir_flag='-L',
		rpath_flag='-rpath',
		output_flag='-o',
		type_map = {
			'executable': '-execute',
			'library': '-dylib',
			'extension': '-bundle',
			'collection': '-r',
		},
	):
	"""
	Command constructor for Mach-O link editor provided on Apple MacOS X systems.
	"""
	get = context.get
	command = [get('reducer', '/usr/bin/ld')]

	typ = get('system.type')
	loutput_type = type_map[typ]
	command.append(loutput_type)

	command.extend([libdir_flag+filepath(x) for x in context['system.library.directories']])

	command.extend((output_flag, filepath(output)))
	if typ == 'executable':
		command.append('/usr/lib/crt1.o')

	command.extend(inputs)

	command.extend([link_flag+filepath(x) for x in context.get('system.library.set', ())])
	command.append('-lSystem')
	return command

def unix_link_editor(context, output, inputs,
		verbose=True,
		filepath=str,
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

		static='-Bstatic',
		shared='-Bshareable',

		exe='crt1.o',
		pie='Scrt1.o',

		staticlib_start='crtbeginT.o',
		static_end='crtend.o',

		sharedlib_start='crtbeginS.o',
		sharedlib_stop='crtendS.o',

		libstart='crti.o',
		libstop='crtn.o',
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
	command = [get('reducer', 'ld')]
	add = command.append
	iadd = command.extend

	if verbose:
		add(verbose_flag)

	loutput_type = type_map[get('system.type')]
	if loutput_type:
		add(loutput_type)

	sld = get('system.library.directories', ())
	libdirs = [libdir_flag + filepath(x) for x in sld]

	sls = get('system.library.set', ())
	libs = [link_flag + filepath(x) for x in sls]

	return command + [output_flag, output] + list(map(filepath, inputs)) + libs

if sys.platform == 'darwin':
	link_editor = macosx_link_editor
else:
	link_editor = unix_link_editor

def updated(outputs, inputs, depfile):
	"""
	Return whether or not the &outputs need to be updated.
	"""
	for x in outputs:
		if not x.exists():
			# No such object, not updated.
			return False
		lm = x.last_modified()
		olm = min(x)

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

def factor_defines(module_fullname, exe_ctx_extension=False):
	modname = module_fullname.split('.')

	return [
		('FACTOR_QNAME', module_fullname),
		('FACTOR_BASENAME', modname[-1]),
		('FACTOR_PACKAGE', '.'.join(modname[:-1])),
	]

def execution_context_extension_defines(module_fullname, target_fullname):
	mp = module_fullname.rfind('.')
	tp = target_fullname.rfind('.')

	return [
		('FACTOR_QNAME', module_fullname),
		('FACTOR_BASENAME', module_fullname[mp+1:]),
		('FACTOR_PACKAGE', module_fullname[:mp]),

		('MODULE_QNAME', target_fullname),
		('MODULE_PACKAGE', target_fullname[:tp]),
	]

def initialize(context:str, role:str, module:libdev.Sources):
	"""
	Initialize a context for use by &transform and &reduce.

	Given a &context name and a &role, initialize a construction context for producing the
	target of the given &module.
	"""
	global merge

	# Factor dependencies stated by imports.
	td = list(module.dependencies())

	# Categorize the module's dependencies.
	incdirs = [include.directory]
	probes = []
	libs = []
	refs = []
	for x in td:
		if isinstance(x, libfactor.IncludesModule):
			incdirs.append(x.sources)
		elif isinstance(x, libfactor.ProbeModule):
			probes.append(x)
		elif isinstance(x, libfactor.SystemModule) and x.system_object_type == 'library':
			libs.append(x)
		else:
			refs.append(x)

	work = libfactor.cache_directory(module, context, role, 'x').container
	parameters = {
		'module': module,
		'role': role,
		'name': context,
		'system.type': getattr(module, 'system_object_type', None),

		'probes': probes,
		'libraries': libs,
		'references': refs,

		'transform': compiler_collection,
		'system.include.directories': incdirs,
		'system.library.directories': [],
		'system.library.set': set(),

		'compiler.preprocessor.defines': [
			('F_ROLE', role),
			('F_ROLE_ID', 'F_ROLE_' + role.upper() + '_ID'),
		],

		'reduction': module.output(context, role),
		'locations': {
			'sources': module.sources,
			'work': work,
			'objects': libfactor.cache_directory(module, context, role, 'objects'),
			'libraries': libfactor.cache_directory(module, context, role, 'lib'),
			'logs': libfactor.cache_directory(module, context, role, 'log'),
			'dependencies': libfactor.cache_directory(module, context, role, 'dl'),
		}
	}
	libdir = parameters['locations']['libraries']

	# Full set of regular files in the sources location.
	if parameters['locations']['sources'].exists():
		parameters['sources'] = parameters['locations']['sources'].tree()[1]

	# Local dependency set comes first.
	parameters['system.library.directories'] = [parameters['locations']['libraries']]

	for probe in probes:
		report = probe.report(probe, 'inherit', role, module)
		merge(parameters, report) # probe parameter merge

	for lib in libs:
		libname = identity(lib)
		parameters['system.library.set'].add(libname)

	if libpython in probes:
		parameters['execution_context_extension'] = True
		men = parameters['mount_point'] = module.extension_name()
		idefines = execution_context_extension_defines(module.__name__, men)
	else:
		parameters['execution_context_extension'] = False
		idefines = factor_defines(module.__name__)

	parameters['compiler.preprocessor.defines'].extend(idefines)

	return parameters

def transform(context, type, filtered=(lambda x,y,z: False)):
	"""
	Using the given set of &processors, prepare the parameters to be given to the
	processor from the probes referenced &module.

	The &context and &role parameters define the perspective that the target is to
	be built for; cache directories are referenced and created using these parameters.

	[ Parameters ]
	/context
		The construction context to base the transformation on.
	/type
		The type of transformation to perform.
	"""
	global languages, include

	if 'sources' not in context:
		return

	loc = context['locations']
	emitted = set([loc['logs'], loc['objects']])

	yield ('directory', loc['logs'])
	yield ('directory', loc['objects'])
	xf = context.get('transform')

	commands = []
	for src in context['sources']:
		fnx = src.extension
		if fnx in {'h'} or src.identifier.startswith('.'):
			# Ignore header files and dot-files.
			continue

		lang = languages.get(src.extension)
		obj = libroutes.File(loc['objects'], src.points)
		depfile = libroutes.File(loc['dependencies'], src.points)

		if filtered(obj, src, depfile):
			continue

		logfile = libroutes.File(loc['logs'], src.points)

		for x in (obj, depfile, logfile):
			d = x.container
			if d not in emitted:
				emitted.add(d)
				yield ('directory', d)

		genobj = functools.partial(xf, language=lang)

		# compilation
		go = {}
		compilation = genobj(context, obj, (src,))

		yield ('execute', compilation, logfile)

def reduce(context):
	"""
	Construct the operations for reducing the object files created by &transform
	instructions into a set of targets that can satisfy
	the set of dependents.

	[ Parameters ]
	/context
		The construction context created by &initialize.
	"""

	role = context['role']
	# target library directory containing links to dependencies
	locs = context['locations']
	libdir = locs['libraries']
	output = context['reduction']

	if 'sources' not in context:
		# Nothing to reduce.
		return

	yield ('directory', output.container)
	yield ('directory', libdir)

	libs = []

	for x in context['libraries']:
		# Create symbolic links inside the target's local library directory.
		# This is done to avoid a large number of -L options in targets
		# with a large number of dependencies.

		# Explicit link of factor.
		libdep = x.output(context['name'], role)
		li = identity(x)
		lib = libdir / library_filename(sys.platform, li)
		yield ('link', libdep, lib)
		libs.append(li)

	# Discover the known sources in order to identify which objects should be selected.
	objdir = locs['objects']
	objects = [
		libroutes.File(objdir, x.points) for x in context['sources']
		if x.extension not in {'h'} and not x.identifier.startswith('.')
	]

	yield ('execute', link_editor(context, output, objects), locs['logs'] / 'reduction')

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
	dispatches the work to be performed for completion.

	! DEVELOPER:
		Primarily, this class traverses the directed graph constructed by imports
		performed by the target modules being built. It works specifically with
		&.libfactor.load modules, and should be generalized.
	"""

	def __init__(self, context, role, modules):
		self.failures = 0
		self.cx_context = context
		self.cx_role = role
		self.modules = modules
		# Manages the dependency order.
		self.sequence = sequence([x[1] for x in modules])

		self.tracking = collections.defaultdict(list) # module -> sequence of sets of tasks
		self.progress = collections.Counter()

		self.process_count = 0 # Track available subprocess slots.
		self.process_limit = 4
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

	def collect(self, module, dependencies=()):
		"""
		Collect all the work to be done for building the desired targets.
		"""
		context = self.cx_context # [construction] context name
		tracks = self.tracking[module]

		if context is None:
			if getattr(module, 'execution_context_extension', False):
				context = python_triplet
			else:
				# Default 'host' context.
				context = 'inherit'
		else:
			# context was explicitly stated meaning
			# extension modules are built for mounting.
			pass

		if isinstance(module, libfactor.ProbeModule):
			# Needs to be transformed into a job.
			# Probes are deployed per dependency.
			probe_set = [('probe', module, x) for x in dependencies]
			tracks.append(probe_set)
		else:
			ctx = initialize(context, self.cx_role, module)
			xf = list(transform(ctx, None))
			rd = list(reduce(ctx))
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

		key = module.key(module, self.cx_context or 'inherit', self.cx_role, dep)
		reports = module.retrieve(self.cx_context or 'inherit', self.cx_role)

		if key in reports:
			# Needed report is cached.
			self.progress[module] += 1
		else:
			xreport = module.deploy(module, self.cx_context or 'inherit', self.cx_role, dep)
			reports[key] = xreport
			if xreport is not None:
				# &None indicates constant probe; &report will build on demand.
				module.record(reports, self.cx_context or 'inherit', self.cx_role)

			self.progress[module] += 1

	def process_execute(self, instruction):
		module, (typ, cmd, log) = instruction
		assert typ == 'execute'
		strcmd = tuple(map(str, cmd))

		with log.open('wb') as f:
			f.write(b'[Command]\n')
			f.write(' '.join(strcmd).encode('utf-8'))
			f.write(b'\n\n[Standard Error]\n')

			ki = libsys.KInvocation(str(cmd[0]), strcmd)
			with open('/dev/null', 'rb') as ci, open('/dev/null', 'wb') as co:
				pid = ki(fdmap=((ci.fileno(), 0), (co.fileno(),1), (f.fileno(),2)))
				sp = libio.Subprocess(pid)

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
