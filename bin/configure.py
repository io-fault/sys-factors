"""
Configure the initialization of the construction context.
"""
import sys
import functools
import shell_command

from ...routes import library as libroutes
from ...xml import library as libxml
from .. import libprobe
from .. import libconstruct

compiler_collections = {
	'clang': (
		'c', 'c++', 'objective-c', 'objective-c++',
		'fortran', 'ada', # via dragonegg
	),
	'gcc': (
		'c', 'c++', 'objective-c', 'fortran', 'ada', 'java',
	),
	'icc': (
		'c', 'c++',
	),
	'egcs': (
		'c', 'c++',
	),
	'cl.exe': (
		'c', 'c++',
	),
}

compiler_collection_preference = ('clang', 'gcc', 'icc', 'cl.exe')

linkers = {
	'lld': (
		'objects',
	),
	'ld': (
		'objects',
	),
}

linker_preference = ('lld', 'ld')

assemblers = {
	'yasm': (),
	'nasm': (),
	'as': (),
}

environment = {
	'CC': 'compiler_collections',
	'LINKER': 'system_linkers',
	'STRIP': 'strip',
	'OBJCOPY': 'objcopy',
}

pyrex_compilers = {
	'cython',
}

haskell_compilers = {
	'ghc': ('haskell',),
}

def debug_isolate(self, target):
	dtarget = target + '.dSYM'
	return dtarget, [
		('dsymutil', target, '-o', dtarget)
	]

def debug_isolate(self, target):
	"""
	Isolate debugging information from the target.
	"""
	debugfile = target + '.debug'

	return [
		(objcopy, '--only-keep-debug', target, debugfile),
		(strip, '--strip-debug', '--strip-unneeded', target),
		(objcopy, '--add-gnu-debuglink', target, debug),
	]

# libconstruct directory ->
	# context ->
		# role ->
			# purpose ->
				# default language handler
				# role file
				# language -> parameters

def select(paths, possibilities, preferences):
	global libprobe

	found, missing = libprobe.search(paths, tuple(possibilities))
	if not found:
		return None
	else:
		for x in preferences:
			if x in found:
				path = found[x]
				name = x
				break
		else:
			# select one randomly
			name = tuple(found)[0]
			path = found[name]

	return name, path

runtime_objects = set([
	'crt0.o', # No constructor support.
	'crt1.o', # Constructor Support.
	'Scrt1.o', # PIE.
	'gcrt1.o',
	'crt1S.o', # Not sure how this is used.

	'crtbeginT.o', # Apparently used for statically linked executables.
	'crtend.o',

	'crtbeginS.o',
	'crtendS.o',

	'crti.o',
	'crtn.o',
])

def main(name, args, paths=None):
	global libroutes
	import os

	if args:
		libconstruct_dir, = args
	else:
		libconstruct_dir = libconstruct.root_context_directory()

	ctx = libconstruct_dir / 'host'

	if paths is None:
		paths = libprobe.environ_paths()

	# default command
	if 'CC' in os.environ:
		cc = libroutes.File.from_absolute(os.environ['CC'])
		ccname = cc.identifier
	else:
		ccname, cc = select(paths, compiler_collections, compiler_collection_preference)
	ldname, ld = select(paths, linkers, linker_preference)

	bindir = cc.container
	ccprefix = bindir.container

	# gather compiler information.
	data = shell_command.shell_output(str(cc) + ' --version').split('\n')
	version_line = data[0]
	cctype, version_spec = version_line.split(' version ')
	version_info, release = version_spec.split('(', 1)
	release = release.strip('()')
	version_info = version_info.strip().split('.', 3)

	if cctype == 'Apple LLVM':
		# rename to clang.
		ccname = 'clang'

	# Extract the default target from the compiler.
	target = None
	for line in data:
		if line.startswith('Target:'):
			target = line
			break
	else:
		target = None
		print('no target in compiler collection version')

	if target:
		target = target.split(':', 1)
		target = target[1].strip()

	# Analyze the library search directories.
	# Primarily interested in finding the crt*.o files for linkage.
	data = shell_command.shell_output(str(cc) + ' -print-search-dirs').split('\n')
	data = [x.split('=', 1) for x in data]
	data = dict([(k.strip(' =:'), v.split(':')) for k, v in data])
	root = libroutes.File.from_absolute('/')

	libdirs = [libroutes.File.from_relative(root, str(x).strip('/')) for x in data['libraries']]
	libdirs.extend(map(libroutes.File.from_absolute,
		('/lib', '/usr/lib',))) # Make sure likely directories are included.

	# scan for system objects (crt1.o, crt0.o, etc)
	found, missing = libprobe.search(libdirs, runtime_objects)
	prepare = lambda x: tuple(map(str, [y for y in x if y]))

	core = {
		'system': {
			# subject data
			'platform': target,

			'reference-types': {'weak', 'lazy', 'upward', 'default'},

			# Formats to build for targets.
			# Fragments inherit the code type.
			'formats': {
				'executable': 'pie',
				'library': 'pic',
				'extension': 'pic',
			},

			# objects used to support the construction of system targets
			# The split (prefix objects and suffix objects) is used to support
			# linkers where the positioning of the parameters is significant.
			'objects': {
				'library': {
					'pdc': [
						prepare((found.get('crti.o'), found.get('crtbegin.o')),),
						prepare((found.get('crtend.o'), found.get('crtn.o')),),
					],
					'pic': [
						prepare((found.get('crti.o'), found.get('crtbeginS.o')),),
						prepare((found.get('crtendS.o'), found.get('crtn.o')),),
					],
				},
				'extension': {
					'pic': [
						prepare((found.get('crti.o'), found.get('crtbeginS.o')),),
						prepare((found.get('crtendS.o'), found.get('crtn.o')),),
					],
				},
				# fragments do not have requirements.
				'fragment': None,
			},

			# subject interfaces.
			'reductions': {
				None: {
					'interface': libconstruct.__name__ + '.link_editor',
					'type': 'linker',
					'name': ldname,
					'command': str(ld),
					'defaults': {},
				}
			},

			'transformations': {
				None: {
					'interface': libconstruct.__name__ + '.compiler_collection',
					'type': 'collection',
					'name': ccname,
					'implementation': cctype,
					'version': version_info,
					'release': release,
					'command': str(cc),
					'defaults': {},
				},
			},
		}
	}

	if sys.platform == 'darwin':
		core['system']['objects']['executable'] = {
			'pie': [
				prepare((found.get('crt1.o'), found.get('crti.o'), found.get('crtbeginS.o')),),
				prepare((found.get('crtendS.o'), found.get('crtn.o')),),
			],
		}
	else:
		# FreeBSD and many Linux systems.
		core['system']['objects']['executable'] = {
			# PDC or PIE based executables. PIC is, essentially, PIE.
			# PDC does not mean that the library is a (completely) statically link binary.
			'pdc': [
				prepare((found.get('crt1.o'), found.get('crti.o'), found.get('crtbegin.o')),),
				prepare((found.get('crtend.o'), found.get('crtn.o')),),
			],
			'pie': [
				prepare((found.get('Scrt1.o'), found.get('crti.o'), found.get('crtbeginS.o')),),
				prepare((found.get('crtendS.o'), found.get('crtn.o')),),
			],
		}

	import pprint
	pprint.pprint(core)

	S = libxml.Serialization()
	D = S.switch('data:')
	xml = b''.join(
		S.root('libconstruct',
			S.element('context',
				libxml.Data.serialize(D, core),
			),
			('xmlns', 'https://fault.io/xml/libconstruct'),
			('xmlns:data', 'https://fault.io/xml/data'),
		)
	)
	rolefile = ctx / 'core.xml'

	with rolefile.open('wb') as f:
		f.write(xml)

	# Initialize lib directory for context libraries.
	ctxlib = ctx / 'lib'
	ctxlib.init('directory')
	ctxinc = ctx / 'include'
	ctxinc.init('directory')

if __name__ == '__main__':
	import sys
	main(sys.argv[0], sys.argv[1:])
