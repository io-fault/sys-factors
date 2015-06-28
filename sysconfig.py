"""
@:stdlib.sysconfig inspired toolset.
"""
import sys
import shutil
import os.path
import functools
import subprocess

class Toolset(object):
	"""
	Toolset implementation that uses sysconfig information in order to compile and link
	C-API extensions.
	"""

	class ToolError(Exception):
		"""
		Exception raised by construction Tools.
		"""
		def __init__(self, stage, target, log):
			self.stage = stage
			self.target = target
			self.log = log

		def __str__(self):
			msg = "could not {0.stage} '{0.target}'\n".format(self)
			msg += "***\n  ".format(self)
			msg += '  '.join(self.log.splitlines(True))
			msg += '\n***'
			return msg

	role = None

	role_compile_flags = {
		'factor': ('-O3', '-g'),
		'debug': ('-g',),
		'test': ('--coverage', '-g', '-O0', '-ftest-coverage', '-fprofile-arcs'),
	}

	role_link_flags = {
		'test': ('--coverage', '-ftest-coverage', '-fprofile-arcs'),
		'factor': (),
	}

	compile_output_extension = '.o'

	@property
	@functools.lru_cache(1)
	def compiler(self):
		import sysconfig
		return sysconfig.get_config_var('CC')

	@property
	@functools.lru_cache(1)
	def sc_link_command(self):
		import sysconfig
		return tuple(sysconfig.get_config_var('BLDSHARED').split())

	@property
	@functools.lru_cache(1)
	def python_include_directory(self):
		import sysconfig
		return sysconfig.get_config_var('INCLUDEPY')

	@property
	@functools.lru_cache(1)
	def linker(self):
		return self.sc_link_command[0]

	@property
	@functools.lru_cache(1)
	def ldflags(self):
		return self.sc_link_command[1:]

	def __init__(self, role = 'factor'):
		self.role = role

	def compile(self,
		target, type, *filenames,
		defines = (),
		includes = (),
		directories = (),
		framework_directories = (),
		compiler = None
	):
		"""
		:param defines: A sequence of key-value pairs that make up parameter defines.
		:type defines: (:py:class:`str`, :py:class:`str`)
		:param includes: A sequence of files that will be directly included in the source.  (-include)
		:type includes: :py:class:`str`
		:param frameworks: A sequence of frameworks to use for compilation. (-F)
		:type frameworks: (:py:class:`str`)
		:param directories: A sequence of include directories. (-I)
		:type directories: :py:class:`str`
		"""
		flags = ('-v', '-fPIC',)
		if sys.platform == 'darwin' and type == 'objc':
			# assume macosx
			plat = ('-framework', 'Foundation')
		else:
			plat = ()

		if compiler is None:
			cc = self.compiler
			if cc is None:
				cc = 'clang'
		else:
			cc = compiler

		if 'clang' in cc:
			shhh = ('-Warray-bounds',) # PyTuple_SET_ITEM() triggers this.
		else:
			shhh = ()

		# on freebsd, this somehow gets packed into the CC variable...
		# XXX: python on freebsd workaround
		if cc.endswith('pthread'):
			cc = cc.rsplit(maxsplit=1)[0]
			flags += ('-pthread',)

		ldirectories = ('-I' + self.python_include_directory,)
		ldirectories += tuple([
			'-I' + x
			for x in directories
		])

		ldefines = tuple([
			'-D' + (k if v is None else k + '=' + v)
			for k, v in defines
		])

		lincludes = []
		for x in includes:
			lincludes.extend(('-include', x,))
		lincludes = tuple(lincludes)

		return [(cc,) + flags + shhh + self.role_compile_flags.get(self.role, ()) + plat \
			+ ldirectories + ldefines + lincludes \
			+ ('-o', target, '-c') + filenames]

	def link(self,
		target,
		*filenames,
		libraries = (),
		directories = (),
		objects = (),
		framework_directories = (),
		frameworks = (),
		linker = None
	):
		"""
		:param directories: A sequence of library directories. (-L)
		:type directories: (:py:class:`str`)
		:param libraries: A sequence of libraries to dynamically link against the target. (-l)
		:type libraries: :py:class:`str`
		:param frameworks: A sequence of frameworks to use for linkage; library sets (-framework)
		:type frameworks: (:py:class:`str`)
		:param frameworks: A sequence of framework directories to use for linkage. (-F)
		:type frameworks: (:py:class:`str`)
		"""
		import sysconfig # avoid module overhead unless it's needed.

		if sys.platform == 'darwin' and False:
			# assume macosx
			plat = ('-framework', 'Foundation')
		else:
			plat = ()

		link = tuple(sysconfig.get_config_var('BLDSHARED').split())
		if linker is not None:
			link = (linker,) + link[1:]

		pyversion = sysconfig.get_config_var('VERSION') or ''.join(map(str, sys.version_info[:2]))
		pyspec = 'python' + pyversion + sys.abiflags

		ldirectories = tuple(['-L' + x for x in directories])
		llibraries = tuple(['-l' + x for x in libraries])
		lobjects = tuple(objects)

		pylib = ('-l' + pyspec,)

		role_flags = self.role_link_flags.get(self.role, ())

		return [link + role_flags + plat + pylib + \
			ldirectories + llibraries + ('-v', '-o', target) + filenames + objects]

	def stage(self,
		id, target, logfile, reference,
		popen = subprocess.Popen,
		exists = os.path.exists,
	):
		"""
		Execute the stage recording progress information to the given logfile path.
		"""
		# stdout/stderr sent to the logfile.
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
					with open(logfile, 'r') as rlog:
						raise self.ToolError(id, target, rlog.read())

		if not exists(target):
			with open(logfile, 'rb') as f:
				log = f.read().decode('utf-8', errors='replace').strip()
			raise self.ToolError(id, target, log)
