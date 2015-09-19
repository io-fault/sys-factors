"""
Manage the process of constructing operating system executables and libraries.
Bootstrap is used to create the necessary dependencies for &.libconstruct.
"""
import sys
import os.path
import subprocess

# The default build role.
role = 'debug' # default build role; can be updated.

# Specifically for identifying files to be compiled.
extensions = {
	'c': ('c',),
	'c++': ('c++', 'cxx', 'cpp'),
	'objective-c': ('m',),
	'ada': ('ads', 'ada'),
	'assembly': ('asm',),
	'bitcode': ('bc',),
}

languages = {}
for k, v in extensions.items():
	for y in v:
		languages[y] = k

collection = (
	'cc', 'gcc', 'msvs', 'llvm'
)

commands = {
	'compile': {
		'asm': (
			{'yasm', 'nasm', 'as'},
			('as',),
		),
		'c': (
			{'cc', 'gcc', 'clang', 'egcs'},
			('clang', 'cc',)
		),
		'c++': (
			{'c++', 'gc++', 'clang++',},
			('clang++',)
		)
	},
	'link': {
		
	}
}

environment = {
	'c': 'CC',
	'ld': 'LINKER',
	'strip': 'STRIP',
	'objcopy': 'OBJCOPY',
}

x = dict(
	cwindows = 'cl.exe',
	compile = ('cl.exe', '/c'),
	link = ('cl.exe',),
	debug_compile = '/Yd',
	csource = '/Tc',
	cxxsource = '/Tp',
)

systems = {

}

def select_role():
	# use override if available; otherwise, use global role in this module
	if role is None:
		default_role = sys.modules[__name__].role
		if default_role is None:
			role = ('debug' if __debug__ else 'factor')
		else:
			role = default_role

def gather(objdir, srcdir, suffixes, suffix_delimiter='.', join=os.path.join):
	"Recursive acquire sources for compilation and build out objects."
	os.makedirs(objdir, exist_ok = True)
	prefix = len(srcdir)

	for path, dirs, files in os.walk(srcdir):
		# build out sub-directories for object cache
		for x in dirs:
			if x == '__pycache__':
				# there shouldn't be __pycache__ directories here, but ignore anyways
				continue

		for x in files:
			suffix = None

			suffix_position = x.rfind(suffix_delimiter)
			if suffix_position == -1:
				# no suffix delimiter
				continue
			else:
				# extract suffix; continue if it's not a recognized language
				suffix = x[suffix_position+1:]
				if suffix not in languages:
					continue

			srcpath = join(srcdir, path, x)
			src_suffix = srcpath[prefix+1:][:-(len(suffix)+len(suffix_delimiter))]
			objpath = join(objdir, src_suffix) + '.o'
			objpathdir = os.path.dirname(objpath)
			if not os.path.exists(objpathdir):
				os.makedirs(objpathdir, exist_ok = True)
			yield languages[suffix], srcpath, objpath

class Toolchain(object):
	"""
	Toolchain for compiling and linking executables, shared libraries, and dynamically
	loaded libraries.
	"""

	# -fPIC is always used for bootstrapped python extensions
	role_compile_flags = {
		'factor': ('-O3', '-g'),
		'debug': ('-O0', '-g'),
		'test': ('-O0', '-g'),
		'analysis': ('--coverage', '-O0', '-g'),
	}

	role_link_flags = {
		'analysis': ('--coverage', '-ftest-coverage', '-fprofile-arcs'),
		'factor': (),
	}

	@classmethod
	def cdarwin(typ, t, language):
		return (typ.default_compiler(), '-x', language)

	@classmethod
	def cunix(typ, t, language):
		return (typ.default_compiler(), '-x', language)

	@classmethod
	def ldll(typ, t, name, version = None, loader = None):
		"Link DLL libraries on Microsoft systems."
		if t == 'bin':
			tfalgs = ()
			suffix = 'exe'
			placement = 'precede'
		elif t == 'lib':
			tflags = ('/dll',)
			suffix = 'dll'
			placement = 'precede'
		elif t == 'libexec':
			tflags = ('/dll',)
			suffix = 'dyn'
			placement = 'precede'

		return placement, suffix, (typ.default_linker(),)

	@classmethod
	def ldylib(typ, t, name, version = None, loader = None):
		"Link .dylib libraries. (macosx/darwin)"
		if t == 'bin':
			tflags = ('-execute', '-lcrt1.o')
			suffix = 'exe'
			placement = 'proceed'
		elif t == 'lib':
			tflags = ('-dylib', '-dead_strip_dylibs',)
			suffix = 'dylib'
			placement = 'precede'
		elif t == 'libexec':
			suffix = 'dylib'
			placement = 'precede'

			if loader is None:
				# Assume unknown or unimportant.
				# Many platforms don't require knowledge of the loader.
				tflags = ('-bundle', '-undefined', 'dynamic_lookup',)
			else:
				tflags = ('-bundle', '-bundle_loader', loader,)

		return placement, suffix, (typ.default_linker(), '-t') + tflags + ('-framework', 'Foundation')

	@classmethod
	def lelf(typ, t, name, version = None, loader = None):
		"Link ELF libraries. (shared objects on most unix systems)"
		if t == 'bin':
			# default is executable
			tflags = ()
			suffix = 'exe'
			placement = 'proceed'
		elif t  == 'lib' and version is not None:
			# shared, soname'd with version ("libname.so.M.N")
			vstr = '.'.join(map(str, version[:2]))
			tflags = ('-shared', '-soname',  '.so.'.join((name, vstr)))
			suffix = 'so'
			placement = 'proceed'
		else:
			tflags = ('-shared',)
			suffix = 'so'
			placement = 'proceed'

		return placement, suffix, (typ.default_linker(),) + tflags + ('-framework', 'Foundation')

	if sys.platform == 'darwin':
		compiler = cdarwin
		_linker = ldylib
	elif sys.platform == 'win32':
		#compiler = cwin
		_linker = ldll
	else:
		compiler = cunix
		_linker = lelf

	def linker(self, t, name, version = None, **kw):
		kw['version'] = version
		version_place, suffix, fragment = self._linker(t, name, **kw)

		if version is not None:
			vstr = tuple(map(str, version))
			if version_place == 'proceed':
				pass
			elif version_place == 'precede':
				pass
		else:
			pass

		return name + '.' + suffix, (), fragment

	def compile(self,
		language, target, sources,
		defines = (),
		includes = (),
		directories = (),
		dependency = None,
	):
		"""
		/defines
			A sequence of key-value pairs that make up parameter defines.
			:type defines: (:py:class:`str`, :py:class:`str`)
		/includes
			A sequence of files that will be directly included in the source.
			:type includes: :py:class:`str`
		/directories
			A sequence of include and framework directories. (-I and -F on applicable platforms)
			:type directories: :py:class:`str`
		"""
		flags = ('-v', '-fPIC',)

		cc = self.compiler(self.type, language)

		ldirectories = ()
		ldirectories += tuple(['-I' + x for x in directories])

		ldefines = tuple([
			'-D' + (k if v is None else k + '=' + v)
			for k, v in defines
		])

		lincludes = []
		for x in includes:
			lincludes.extend(('-include', x,))
		lincludes = tuple(lincludes)

		if dependency is not None:
			dflags = ('-MD', '-MT', 'none', '-MF', dependency)
		else:
			dflags = ()

		return cc + flags + dflags + self.role_compile_flags.get(self.role, ()) \
			+ ldirectories + ldefines + lincludes + ('-o', target, '-c') + sources

	def link(self,
		targetdir, name,
		version, objects,
		loader = None,
		libraries = (),
		directories = (),
		frameworks = (),
		linker = None
	):
		"""
		/directories
			A sequence of library and framework directories. (-L, -F on some systems)
			:type directories: (:py:class:`str`)
		/libraries
			A sequence of libraries to dynamically link against the target. (-l)
			:type libraries: :py:class:`str`
		/frameworks
			A sequence of frameworks to use for linkage; library sets (-framework)
			:type frameworks: (:py:class:`str`)
		"""
		basename, canons, link = self.linker(self.type, name, version = version)
		target = os.path.join(targetdir, basename)

		ldirectories = tuple(['-L' + x for x in directories])
		llibraries = tuple(['-l' + x for x in libraries])

		role_flags = self.role_link_flags.get(self.role, ())

		return (
			target, canons,
			link + role_flags + ldirectories + \
			llibraries + ('-v', '-o', target) + tuple(objects)
		)

	if sys.platform == 'darwin':
		def isolate(self, target):
			dtarget = target + '.dSYM'
			return dtarget, [
				('dsymutil', target, '-o', dtarget)
			]
	else:
		def isolate(self, target):
			"""
			Isolate debugging information from the target.
			"""
			oc = self.default_objcopy()
			strip = self.default_strip()

			d = os.path.dirname(target)
			b = os.path.basename(target)
			debug = b + '.debug'

			return [
				(oc, '--only-keep-debug', target, os.path.join(d, debug)),
				(strip, '--strip-debug', '--strip-unneeded', target),
				(oc, '--add-gnu-debuglink', target, debug),
			]

	def stage(self,
		id, target, reference,
		popen = subprocess.Popen,
		exists = os.path.exists,
	):
		"""
		Execute the stage recording progress information to the given logfile path.
		"""
		# stdout/stderr sent to the logfile.
		logfile = target + '.' + id + '.log'

		with open(logfile, 'w') as log:
			pass

		for x in reference:
			with open(logfile, 'a') as log:
				log.write('\n--------\n')
				log.write(' '.join(x))
				log.write('\n--------\n\n')
				log.flush()

				r = popen(x, stdout = log, stderr = subprocess.STDOUT, stdin = None)
				if r.wait() != 0:
					raise abstract.ToolError(id, target, log)

		if not exists(target):
			with open(logfile, 'rb') as f:
				log = f.read().decode('utf-8', errors='replace').strip()
			raise abstract.ToolError(id, target, log)
