"""
Management of target construction jobs using &.libprobe command Matrices.

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
import subprocess
import functools
import itertools
import collections
import contextlib
import importlib

import lxml.etree

from . import libfactor
from . import include

from ..io import library as libio
from ..system import libexecute
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

def python_context(implementation, version_info, abiflags, platform):
	"""
	Construct the triplet representing the Python context for the platform.
	Used to define the context for Python extension modules.
	"""
	pyversion = ''.join(map(str, version_info[:2]))
	return '-'.join((implementation, pyversion + abiflags, platform))

python_triplet = python_context(sys.implementation.name, sys.version_info, sys.abiflags, sys.platform)

def compile_bytecode(target, source):
	global importlib
	pyc_cache = importlib.util.cache_from_source(source)

class Parameters(object):
	"""
	Construction parameters collections for managing compilation and link parameters.

	Provides adaption methods for collecting parameters for a specific compilation stage.
	"""

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

def construction(matrix:libexecute.Matrix, controller=None, environment=None):
	"""
	Generator managing the instantiation of &libsys.KInvocation instances
	used to create the target.

	A single temporary directory with a set of job directories created for
	each task that's ran in order to build the target.
	"""
	ref = None
	ki = None

	with libroutes.File.temporary() as tr:
		for job_id in itertools.count():
			workdir = tr / str(job_id)
			workdir.init('directory')
			ref, *parameters = (yield workdir, ki) # Load a command to apply parameters to.

			workdir.init('directory')
			stderr = workdir / 'stderr'

			for p in parameters:
				for k, v in p.items():
					ref.update(k, v)

			cenv, route, args = ref.render()
			env = {}
			env.update(matrix.environment)
			env.update(cenv)
			env['PWD'] = str(workdir)

			ki = libsys.KInvocation(str(route), args, env)
			src = ref

	# tr gets removed on generator close()

def load(role, route=None):
	"""
	Open the command matrix providing the interfaces for compilation.

	[ Parameters ]
	/role
		The string identifying the role to load.
	/route
		Optional parameter specifying an exact directory containing the
		matrix XML files.
	"""
	if route is None:
		route = libroutes.File.home() / '.fault'
		route = route / 'development-matrix'

	matrixfile = route / (role + '.xml')
	matrixdoc = lxml.etree.parse(str(matrixfile))

	return libexecute.Matrix.from_xml(matrixdoc)

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
	dictionary. The imported system object factor modules are identified as dependencies
	that need to manifested in order to process the subject module.
	"""
	deps = set(collect(module))
	if not deps:
		working.add(module)
		return

	# no dependencies, add to working set.
	tree[module] = deps

	for x in deps:
		inverse[x].add(module)
		traverse(working, tree, inverse, x)

def construct(module, roles, route=None, context=None):
	"""
	Construct the target of the &module for each of the given roles.

	[ Parameters ]
	/module
		The &SystemModule defining the executable, library, module, or extension to construct.

	/roles
		The set of roles to construct.

	/route
		The directory location of the libexecute XML files that define the commands
		to run. Merely passed on to &load.
	"""
	global languages, construction, include

	sources = module.sources
	params = {k:module.__dict__.get(k, None) for k in data_fields}

	typ = getattr(module, 'system_object_type', None)
	if typ in {None, 'system.probe', 'system.includes'}:
		return

	if typ == 'library':
		types = ('library', 'partial')
	else:
		types = (typ,)

	pyext = getattr(module, 'execution_context_extension', None)

	modname = module.__name__.split('.')
	if pyext:
		# The system.extension was identified as a Python extension.
		qname = module.extension_name()
		context = context or python_triplet
		target_defines = [
			'MODULE_QNAME=' + qname,
			'MODULE_BASENAME=' + modname[-1],
			'MODULE_PACKAGE=' + '.'.join(modname[:-1]),
		]
	else:
		context = context or 'inherited'
		target_defines = [
			'MODULE_QNAME=' + module.__name__,
			'MODULE_BASENAME=' + modname[-1],
			'MODULE_PACKAGE=' + '.'.join(modname[:-1]),
		]

	if os.environ.get('FAULT_RECONSTRUCT', None) == '1':
		recon = True
	else:
		recon = False

	# Factor dependencies stated by imports.
	td = list(module.dependencies())
	probes = [x for x in td if isinstance(x, libfactor.ProbeModule)]

	# Iterate over and construct each role to avoid
	# forcing the user to iterate.
	for role in roles:
		compiled = 0
		output = module.output(context, role)
		if output is None:
			continue

		objdir = module.objects(context, role)
		logdir = libfactor.cache_directory(module, context, role, 'log')
		depdir = libfactor.cache_directory(module, context, role, 'odl')
		incdir = [include.directory]

		known_sources = set()

		probe_parameters = {
			probe: probe.report(probe, module, role) for probe in probes
		}

		for x in (logdir, objdir, depdir):
			x.init('directory')

		matrix = load(role, route=route)
		g = construction(matrix); g.send(None)

		for x in td:
			if isinstance(x, libfactor.IncludesModule):
				# Explicit link of factor.
				incdir.append(x.sources)
			else:
				pass

		for src in sources.tree()[1]:
			# XXX: check modifications times/consistency
			fnx = src.extension
			if fnx in {'h'}:
				# Ignore header files.
				continue

			lang = languages[src.extension]
			obj = libroutes.File(objdir, src.points)
			depfile = libroutes.File(depdir, src.points)
			logfile = libroutes.File(logdir, src.points)
			known_sources.add(src.points)

			if obj.exists():
				olm = obj.last_modified()
			else:
				olm = 0

			if not recon and obj.exists():
				if olm < src.last_modified():
					# rebuild if object is older than source.
					pass
				elif depfile.exists():
					# Alter to only pay attention to project and context files.

					ignore = True
					# check identified dependencies if any
					with depfile.open('r') as f:
						pmd = parse_make_dependencies(f.read())
						deps = list(map(libroutes.File.from_absolute, pmd))

					for dep in deps:
						if olm < dep.last_modified():
							ignore = False
							break

					if ignore:
						# skip compilation as object is newer
						# than the source and its dependencies.
						continue
			else:
				# object does not exist, compile into linker input.
				pass

			obj.container.init('directory')
			depfile.container.init('directory')
			logfile.container.init('directory')

			# XXX: apply project and source params

			cmd = matrix.commands['compile.' + lang]
			ref = libexecute.Reference(matrix, cmd)

			params = tuple(probe_parameters.values())

			defines = [
				'F_ROLE=' + role,
				'F_ROLE_ID=F_ROLE_' + role.upper() + '_ID',
			] + target_defines

			# compilation
			lp = cmd.allocate()
			lp['input'].append(src)
			lp['output'] = obj

			lp['compiler.preprocessor.defines'] = defines
			lp['system.include.directories'].extend(incdir)

			compilation = g.send((ref,) + params + (lp,)) + (obj, depfile, logfile)

			# dependencies
			ref = libexecute.Reference(matrix, cmd)
			lp = cmd.allocate()
			lp['input'].append(src)
			lp['output'] = depfile

			lp['compiler.preprocessor.defines'] = defines
			lp['system.include.directories'].extend(incdir)
			lp['compiler.options']['emit_dependencies'] = True
			lp['compiler.options']['exclude_system_dependencies'] = True
			generate_deps = g.send((ref,) + params + (lp,)) + (obj, depfile, logfile.suffix('.dep'))

			yield generate_deps
			yield compilation
			compiled += 1
		else:
			# Aggregate the objects according to the target type.
			if not compiled:
				# Nothing compiled, no new link to perform.
				continue

			output.container.init('directory')

			# target library directory containing links to dependencies
			libdir = module.libraries(context, role)
			libdir.init('directory')
			libs = []
			data = (getattr(module, 'parameters', None) or {})

			for x in td:
				# Check each target dependency (development factor module imports)
				# and create symbolic links inside the target's local library directory.
				# This is done to avoid a large number of -L options in targets
				# with a large number of dependencies.

				if x.system_object_type in {'system.library', 'system.object'}:
					# Explicit link of factor.
					libdep = x.output(context, role)
					lib = libdir / library_filename(sys.platform, x.name)
					if not lib.exists():
						lib.link(libdep)

					libs.append(x.name)
				else:
					pass

			dynlinks = []

			for typ in types:
				cmd = matrix.commands['link.' + typ]

				params = tuple(probe_parameters.values())

				ref = libexecute.Reference(matrix, cmd)
				lp = cmd.allocate()
				lp['input'].extend([x for x in objdir.tree()[1] if x.points in known_sources])
				rt = matrix.context.get('runtime')
				if rt is not None:
					lp['input'].append(rt)

				lp['output'] = output
				lp['system.library.set'].extend(dynlinks) # explicit dynamic links
				lp['system.library.set'].extend(libs) # from refrenced factor modules
				lp['system.library.set'].extend(matrix.context['libraries'])

				lp['system.library.directories'].append(libdir)
				try:
					from ..stack import apple
					mv = apple.macos_version()
					mv = mv.rsplit('.', 1)[0] + '.0'
					lp['macosx.version.minimum'] = (mv,)
				except ImportError:
					pass

				yield g.send((ref,) + params + (lp,)) + (output, None, (logdir / 'link'))
				g.close()

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

def update(role, module, reconstruct=False):
	"""
	Update the target module's cache if necessary.

	For a given role and module, check if the sources or dependencies have been modified since
	the factor was created.
	"""
	if isinstance(module, libfactor.ProbeModule):
		return
	output = module.output(role)

	cwd = os.getcwd()
	try:
		for pwd, ki, out, dep, log in construct(module, (role,)):
			os.chdir(str(pwd))

			with contextlib.ExitStack() as xs:
				lf = xs.enter_context(open(str(log), 'wb'))
				ni = xs.enter_context(open('/dev/null', 'rb'))
				no = xs.enter_context(open('/dev/null', 'wb'))

				pid = ki(fdmap=((ni.fileno(),0), (no.fileno(), 1), (lf.fileno(), 2)))

			r = os.waitpid(pid, 0)
	finally:
		os.chdir(cwd)

def manage(root, *roles):
	global update

	tree = dict()
	inverse = collections.defaultdict(set)
	working = set()
	traverse(working, tree, inverse, root)

	while working:
		module = next(iter(working))
		for x in roles:
			update(x, module)
		working.discard(module)

		for deps in inverse[module]:
			tree[deps].discard(module)
			if not tree[deps]:
				working.add(deps)
				del tree[deps]
