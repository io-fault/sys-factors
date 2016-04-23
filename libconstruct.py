"""
Management of target construction jobs using &.libprobe command Matrices.
"""
import os
import sys
import subprocess
import functools
import itertools
import lxml.etree

from . import libfactor
from . import libpxe

from ..io import library as libio
from ..system import libexecute
from ..system import library as libsys
from ..routes import library as libroutes

class ToolError(Exception):
	"""
	Exception raised when a construction tools signalled failure.

	[ Properties ]
	/exit_code
		The exit code that the tool returned.
	/standard_error
		The raw binary data emitted into the standard error file descriptor.
	"""

	@property
	def xml(self):
		"""
		The &standard_error interpreted as an XML document for introspecting runtime errors reported
		by the tool.
		"""

	def __init__(self, exit_code, stderr):
		self.exit_code = exit_code
		self.standard_error = stderr

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

from . import include
extension_compilation = {
	'system.include.directories': (include.directory,),
}
del include

def roles(module):
	"""
	Identify the role to use for the given module.
	"""
	return ('factor',)

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
			ref, *parameters = (yield ki) # Load a command to apply parameters to.

			workdir = tr / str(job_id)
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

			print(route, args, env)
			ki = libsys.KInvocation(str(route), args, env)
			src = ref

	# tr gets removed on generator close()

def dependencies(module, object, source):
	"""
	Returns a set of known dependencies of a given file.
	"""
	return []

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

def construct(module, roles, route=None):
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
	global languages, construction

	sources = module.sources
	params = {k:module.__dict__.get(k, None) for k in data_fields}

	typ = module.system_object_type
	if typ == 'library':
		types = ('library', 'archive')
	else:
		types = (typ,)

	if libpxe in module.__dict__.values():
		pyext = True
	else:
		pyext = False

	modname = module.__name__.split('.')
	target_includes = module.includes
	if pyext:
		qname = ''.join(module.__name__.split('.extensions'))
		target_defines = [
			'MODULE_QNAME=' + qname,
			'MODULE_BASENAME=' + modname[-1],
			'MODULE_PACKAGE=' + '.'.join(modname[:-1]),
		]
	else:
		target_defines = [
			'MODULE_QNAME=' + module.__name__,
			'MODULE_BASENAME=' + modname[-1],
			'MODULE_PACKAGE=' + '.'.join(modname[:-1]),
		]

	# Iterate over and construct each role to avoid
	# forcing the user to iterate.
	for role in roles:
		output = module.output(role)
		objdir = module.objects(role)
		matrix = load(role, route=route)
		g = construction(matrix)
		g.send(None)

		td = list(module.dependencies())

		for src in sources.tree()[1]:
			# XXX: check modifications times/consistency
			fnx = src.extension
			if fnx in {'h'}:
				# Ignore header files.
				continue

			lang = languages[src.extension]
			obj = libroutes.File(objdir, src.points)
			if obj.exists():
				olm = obj.last_modified()
			else:
				olm = 0

			if obj.exists():
				if olm < src.last_modified():
					# rebuild if object is older than source.
					pass
				else:
					ignore = True
					# check identified dependencies if any
					for dep in dependencies(module, obj, src):
						if olm < dep.last_modified():
							ignore = False
							break
					if ignore:
						# skip compilation as object is newer
						# than the source and its dependencies.
						continue
			else:
				obj.container.init('directory')
			# XXX: apply project and source params

			cmd = matrix.commands['compile.' + lang]
			ref = libexecute.Reference(matrix, cmd)

			params = tuple([
				x.compilation_parameters(role, lang) for x in td
				if isinstance(x, libfactor.ProbeModule)
			])

			# local parameters
			lp = cmd.allocate()
			lp['input'].append(src)
			lp['output'] = obj

			lp['compiler.preprocessor.defines'] = [
				'F_ROLE_ID=F_ROLE_' + role.upper() + '_ID',
			] + target_defines

			ki = g.send((ref,) + params + (lp,))
			pid = ki(fdmap=((os.dup(0),0), (os.dup(1), 1), (os.dup(2), 2)))
			r = os.waitpid(pid, 0)
		else:
			# Aggregate the objects according to the target type.
			output.container.init('directory')
			libdir = module.libraries(role)
			libdir.init('directory')
			libs = []

			for x in td:
				if x.system_object_type == 'system.library':
					# Explicit link of factor.
					libdep = x.output(role)
					lib = libdir / ('lib' + x.name + '.so')
					if not lib.exists():
						lib.link(libdep)

					libs.append(x.name)
				else:
					pass

			dynlinks = []

			for typ in types:
				cmd = matrix.commands['link.' + typ]

				params = tuple([
					x.link_parameters(role, typ) for x in td
					if isinstance(x, libfactor.ProbeModule)
				])

				ref = libexecute.Reference(matrix, cmd)
				lp = cmd.allocate()
				lp['input'].extend(objdir.tree()[1])
				lp['output'] = output
				lp['system.libraries'].append('c')
				lp['system.libraries'].extend(dynlinks) # explicit dynamic links
				lp['system.libraries'].extend(libs) # from refrenced factor modules

				lp['system.library.directories'].append(libdir)
				lp['macosx.version.minimum'] = ['10.11']

				ki = g.send((ref, lp) + params)
				pid = ki(fdmap=((os.dup(0),0), (os.dup(1), 1), (os.dup(2), 2)))
				r = os.waitpid(pid, 0)
				print(r)
				g.close()
