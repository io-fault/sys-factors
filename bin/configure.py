"""
Configure the command matrix used to build system libraries and executables from source code.

Similar to (system:command)`configure` scripts distributed with projects, &.bin.configure
probes the system for executables, compilers, headers, and libraries in order to identify
how construction of targets should happen. However, &.bin.configure is distinct in that
the configuration generated is stored relative to the user. The checks that take place
are relatively global; it is intended that the system define how to perform compilation while
&.bin.configure attempts to figure out how the system might do so using common driver interfaces.

The &..system.libexecute.Matrix built by &.bin.configure is serializaed into the user's home directory
(system:directory)`.fault/development-matrix/default.xml` or the directory designated with command
options. The slot (filename) to use can be configured using (system:environment)`FAULT_DEV_MATRIX`,
and (system:environment)`FAULT_DIRECTORY` to control its container. The selected matrix slot

&.bin.configure uses &.libprobe queries to identify the features of the system and its commands.
"""
import sys
import functools

from ...routes import library as libroutes
from ...system import libexecute
from ...xml import library as libxml
from .. import libprobe

Sequencing = libprobe.Sequencing
Feature = libexecute.Feature

command_output = Feature.construct(
	'output',
	functools.partial(Sequencing.output, name='main', signal='-o'),
	libexecute.Path,
)

command_input = Feature.construct(
	'input',
	functools.partial(Sequencing.input, name='sources'),
	libexecute.Path,
)

darwin_framework_directories = Feature.construct(
	'darwin.framework.directories',
	functools.partial(Sequencing.prefix, signal='-F'),
	libexecute.Directory,
)

# /usr/bin/ld
unix_linker_v1 = [
	Feature.construct(
		'system.library.set',
		functools.partial(Sequencing.prefix, signal='-l'),
		libexecute.File,
	),

	Feature.construct(
		'system.library.directories',
		functools.partial(Sequencing.prefix, signal='-L'),
		libexecute.Directory,
	),

	Feature.construct(
		'system.library.runtime_paths',
		functools.partial(Sequencing.prefix, signal='-rpath'),
		libexecute.Directory,
	),

	Feature.construct(
		'system.extension.loader',
		functools.partial(Sequencing.option, signal=(
			'-bundle_loader'
		)),
		libexecute.File,
	),

	Feature.construct(
		'type',
		functools.partial(Sequencing.selection,
			executable=('' if sys.platform != 'darwin' else '-execute'),
			library=('-shared' if sys.platform != 'darwin' else '-dylib'),
			extension=('-shared' if sys.platform != 'darwin' else '-bundle'),
			partial='-r',
		),
		libexecute.String,
	),

	Feature.construct(
		'elf.parameters',
		functools.partial(Sequencing.assignments, soname='-soname'),
		libexecute.String,
	),

	Feature.construct(
		'darwin.framework.directories',
		Sequencing.void,
		libexecute.Directory,
	),

	Feature.construct(
		'symbol.export',
		functools.partial(Sequencing.precede, signal='-exported_symbol'),
		libexecute.String,
	),

	Feature.construct(
		'symbol.hidden',
		functools.partial(Sequencing.precede, signal='-unexported_symbol'),
		libexecute.String,
	),

	Feature.construct(
		'symbol.required',
		functools.partial(Sequencing.precede, signal='-u'),
		libexecute.String,
	),

	Feature.construct(
		'system.include.directories',
		Sequencing.void,
		libexecute.String
	),

	Feature.construct(
		'system.include.set',
		Sequencing.void,
		libexecute.String
	),

]

macosx_version_minimum = Feature.construct(
	'macosx.version.minimum',
	functools.partial(Sequencing.precede, signal='-macosx_version_min'),
	libexecute.String,
)

if sys.platform == 'darwin':
	unix_linker_v1.append(macosx_version_minimum)
else:
	unix_linker_v1.append(
		Feature.construct('macosx.version.minimum', Sequencing.void, libexecute.String)
	)

unix_c_compiler_v1 = [
	Feature.construct(
		'system.library.directories',
		Sequencing.void,
		libexecute.String
	),

	Feature.construct(
		'system.library.set',
		Sequencing.void,
		libexecute.String
	),

	Feature.construct(
		'system.include.directories',
		functools.partial(Sequencing.prefix, signal='-I'),
		libexecute.Directory,
	),

	Feature.construct(
		'system.include.set',
		functools.partial(Sequencing.precede, signal='-include'),
		libexecute.File,
	),

	Feature.construct(
		'compiler.optimization.target',
		functools.partial(Sequencing.prefix, signal='-O'),
		libexecute.String,
	),

	Feature.construct(
		'compiler.options',
		functools.partial(Sequencing.options,
			debug='-g',
			# gcc
			coverage='-fcoverage-mapping',
			#profile='-fprofile-arcs',
			profile='-fprofile-instr-generate',
			# clang
			#profile='-fprofile-instr-generate',
			#coverage='-fcoverage-mapping',
			assembly='-c',
			position_independent='-fPIC',
			wrap_signed_overflow='-fwrapv',
			emit_dependencies='-M',
			exclude_system_dependencies='-MM',
			freebsd_reentrant='-D_REENTRANT',
		),
		bool,
	),

	Feature.construct(
		'compiler.preprocessor.defines',
		functools.partial(Sequencing.prefix, signal='-D'),
		libexecute.String,
	),

	Feature.construct(
		'compiler.preprocessor.undefines',
		functools.partial(Sequencing.prefix, signal='-U'),
		libexecute.String,
	),

	Feature.construct(
		'compiler.language',
		functools.partial(Sequencing.subcommand, signal='-x'),
		libexecute.String,
	),

	Feature.construct(
		'compiler.language.constraints',
		functools.partial(Sequencing.assignments, standard='-std='),
		libexecute.String,
	),
]

# Currently, it doesn't work on windows, but some work was done in
# discovering the cl.exe options, so construct the features here.
msw_c_compiler_v1 = [
	Feature.construct(
		'system.include.directories',
		functools.partial(Sequencing.prefix, signal='/I'),
		libexecute.Directory,
	),

	Feature.construct(
		'compiler.optimization.target',
		functools.partial(Sequencing.prefix, signal='/O'),
		libexecute.String,
	),

	Feature.construct(
		'compiler.options',
		functools.partial(Sequencing.options,
			debug='/Yd',
			assembly='/c',
		),
		bool,
	),

	Feature.construct(
		'compiler.preprocessor.defines',
		functools.partial(Sequencing.prefix, signal='/D'),
		libexecute.String,
	),

	Feature.construct(
		'compiler.preprocessor.undefines',
		functools.partial(Sequencing.prefix, signal='/U'),
		libexecute.String,
	),

	Feature.construct(
		'compiler.language',
		functools.partial(Sequencing.subcommand, signal=None, c='/Tc', cxx='/Tp'),
		libexecute.String,
	),

	Feature.construct(
		'compiler.language.constraints',
		functools.partial(Sequencing.assignments, standard='-std='),
		libexecute.String,
	),
]

msw_linker_v1 = [
	Feature.construct(
		'defaults',
		functools.partial(Sequencing.subcommand, signal='/dll'),
		libexecute.String,
	),
]

llvm_coverage = [
	Feature.construct(
		'options',
		functools.partial(Sequencing.options, no_color='-no-color'),
		bool,
	),
	Feature.construct(
		'defaults',
		functools.partial(Sequencing.subcommand, signal=None, show=True),
		libexecute.String,
	),
]

darwin_link_options = [
	Feature.construct(
		'options',
		functools.partial(Sequencing.options, executable='-execute'),
		bool,
	)
]

system_linkers = {
	'ld': unix_linker_v1,
}

# Compiler collections are expected compile C/C++/Objective-C
c_compilers = {
	'clang': unix_c_compiler_v1,
	'cc': unix_c_compiler_v1,
	'gcc': unix_c_compiler_v1,
	'egcs': unix_c_compiler_v1,
	'icc': unix_c_compiler_v1,
	'cl.exe': msw_c_compiler_v1,
}

c_compiler_preference = ['clang', 'cc']

common_compiler = None
msw_linker = None

haskell_compilers = {
	'ghc': common_compiler,
}

linkers = {
	'ld': unix_linker_v1,
	'cl.exe': msw_linker,
}

assemblers = {
	'yasm': common_compiler,
	'nasm': common_compiler,
	'as': common_compiler,
}

environment = {
	'c.compiler': 'CC',
	'linker': 'LINKER',
	'strip': 'STRIP',
	'objcopy': 'OBJCOPY',
}

pyrex_compiler_v1 = [
	Feature.construct(
		'version',
		functools.partial(Sequencing.choice, choices={2:('-2',), 3:('-3',)}),
		bool,
	),
	command_input,
	command_output,
]

pyrex_compilers = {
	'cython': pyrex_compiler_v1,
}

if 0:
	# Darwin
	#'-dead_strip_dylibs'

	# dynamic links
	if loader is None:
		# Assume unknown or unimportant.
		# Many platforms don't require knowledge of the loader.
		tflags = ('-bundle', '-undefined', 'dynamic_lookup',)
	else:
		tflags = ('-bundle', '-bundle_loader', loader,)

if 0:
	# shared, soname'd with version ("libname.so.M.N")
	vstr = '.'.join(map(str, version[:2]))
	tflags = ('-shared', '-soname',  '.so.'.join((name, vstr)))

def isolate(self, target):
	dtarget = target + '.dSYM'
	return dtarget, [
		('dsymutil', target, '-o', dtarget)
	]

def isolate(self, target):
	"""
	Isolate debugging information from the target.
	"""

	d = os.path.dirname(target)
	b = os.path.basename(target)
	debug = b + '.debug'

	return [
		(oc, '--only-keep-debug', target, os.path.join(d, debug)),
		(strip, '--strip-debug', '--strip-unneeded', target),
		(oc, '--add-gnu-debuglink', target, debug),
	]

def compiler(ident, route, language, features, role, standard=None):
	"""
	Return a &libexecute.Command instance for a compiler interface
	using the given set of &features.

	Builds the defaults for the command.
	"""

	defaults = {
		'compiler.language': language,
		'compiler.options': {
			'assembly': True,
			'position_independent': True,
		},
		'system.include.directories': (),
		'system.include.set': (),
		'compiler.preprocessor.defines': (),
		'compiler.preprocessor.undefines': (),
		'input': (),
	}

	cmd = libexecute.Command(ident, 'compiler', route, defaults, input=language, output='linker object')
	for x in features:
		cmd.define(x)

	cmd.define(command_output)
	cmd.define(command_input)
	return cmd

def linker(identifier, route, features, target):
	"""
	Return a &libexecute.Command instance for a linker interface
	using the given set of &features.
	"""

	defaults = {
		'system.library.directories': [],
		'system.library.set': [],
		'darwin.framework.directories': [],
		'input': [],
	}

	cmd = libexecute.Command(identifier, 'linker', route, defaults, input='linker object', output=target)
	for x in features:
		cmd.define(x)

	cmd.define(command_output)
	cmd.define(command_input)

	return cmd

c_languages = [
	'c', 'c++', 'objective-c',
]

linkers = [
	'ld',
]

def matrix(role, paths, identifier='system.development'):
	"""
	Construct a new &libexecute.Matrix for system object construction using
	the given environment.

	This generates a base Matrix that will be modified for each toolchain role that
	is stored on the system.
	"""

	m = libexecute.Matrix(identifier, paths)

	present, absent = libprobe.executables(paths, c_compilers)
	for x in c_compiler_preference:
		ccpath = present.pop('clang')

		if ccpath is not None:
			break
	else:
		# no preferred compiler
		if not present:
			print("No C compiler executable found; LLVM's clang is recommended")
			raise SystemExit(202)
		else:
			# no preferred compilers available.
			for cid, ccpath in present.items():
				break

	for x in c_languages:
		cmd = compiler('compile.'+x, ccpath, x, unix_c_compiler_v1, role, standard='c99')
		cmd.defaults['compiler.options']['wrap_signed_overflow'] = True
		m.commands[cmd.identifier] = cmd

		if role == 'optimal':
			cmd.defaults['compiler.optimization.target'] = ('2',)
		elif role == 'debug':
			cmd.defaults['compiler.optimization.target'] = ('0',)
		elif role == 'test' or role == 'survey':
			cmd.defaults['compiler.optimization.target'] = ('0',)
			if role == 'survey':
				cmd.defaults['compiler.options']['profile'] = True
				cmd.defaults['compiler.options']['coverage'] = True

	present, absent = libprobe.executables(paths, linkers)
	lpath = present.pop('ld')

	# executable
	le = 'link.system.executable'
	lc = linker(le, lpath, unix_linker_v1, 'executable')
	m.commands[le] = lc
	d = m.commands['link.system.executable'].defaults
	d['input'].append('/usr/lib/crt1.o')
	d['type'] = 'executable'

	# library weak link
	ll = 'link.system.library'
	cmd = linker(ll, lpath, unix_linker_v1, 'library')
	m.commands[cmd.identifier] = cmd
	d = cmd.defaults
	d['type'] = 'library'

	# dynamic for runtime links
	lx = 'link.system.extension'
	cmd = linker(lx, lpath, unix_linker_v1, 'extension')
	m.commands[cmd.identifier] = cmd
	d = cmd.defaults
	d['type'] = 'extension'

	# partial link objects; used for organizing areas of an executable or library
	lx = 'link.system.object'
	cmd = linker(lx, lpath, unix_linker_v1, 'partial')
	m.commands[cmd.identifier] = cmd
	d = cmd.defaults
	d['type'] = 'partial'

	m.context['role'] = role
	if sys.platform == 'darwin':
		m.context['libraries'] = ['System']
		if role == 'survey':
			m.context['runtime'] = '/x/realm/lib/clang/3.8.0/lib/darwin/libclang_rt.profile_osx.a'
	else:
		m.context['libraries'] = ['c', 'm', 'pthread']
		if role == 'survey':
			m.context['runtime'] = ''

	return m

def main(name, args, paths=None):
	import os
	slots = [
		'optimal',
		'debug', # optimal with low optimizations for enhanced debugging
		'test', # debug with test role defines for enabling dependency injection
		'survey', # test + coverage + profile
		'profile',
		'coverage',
	]

	if paths is None:
		paths = list(map(libroutes.File.from_path, os.environ["PATH"].split(os.pathsep)))

	user = libroutes.File.home()

	for x in slots:
		m = matrix(x, paths)

		matrixfile = user / '.fault' / 'development-matrix' / (x + '.xml')
		matrixfile.init('file')

		xml = b''.join(m.serialize(libxml.Serialization()))
		with matrixfile.open('wb') as f:
			f.write(xml)

if __name__ == '__main__':
	import sys
	main(sys.argv[0], sys.argv[1:])
