"""
Configure the initialization of the construction context.
"""
import os
import sys
import functools
import shell_command

from ...routes import library as libroutes
from ...xml import library as libxml
from .. import libprobe
from .. import libconstruct
from .. import web

javascript_combiners_preference = ['uglifyjs']
web_compiler_collections = {
	'emcc': (
		'c', 'c++', 'objective-c', 'objective-c++',
		'fortran', 'ada', # via dragonegg
	),
}
web_compiler_collection_preference = ('emcc',)
web_linker_preference = ('emcc',)

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

platform = sys.platform.strip('0123456789')

def init(ctx):
	# Initialize lib directory for context libraries.
	for x in ('bin', 'lib', 'include'):
		(ctx / x).init('directory')

	return ctx

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

def select(paths, possibilities, preferences):
	"""
	Select a file from the given &paths using the &possibilities and &preferences
	to identify the most desired.
	"""
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

# These object files are searched for in the directories scraped from
# the compiler collection's -v invocation.
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

def compiler_libraries(compiler, prefix, version, executable, target):
	"""
	Attempt to select the compiler libraries directory containing compiler support
	libraries for profiling, sanity, and runtime.
	"""
	if compiler == 'clang':
		lib = prefix / 'lib' / 'clang' / version / 'lib'
		syslib = lib / platform # Naturally, not always consistent.
		if syslib.exists():
			return syslib
	elif compiler == 'gcc':
		return prefix / 'lib' / 'gcc' / target / version
	else:
		pass

def javascript_subject(paths):
	"""
	Initialize the javascript subject for JavaScript file compilation.

	This primarily means "minification" and mere concatenation, but languages
	targeting JavaScript can be added.
	"""
	jscname, jsc = select(paths, ['uglifyjs'], javascript_combiners_preference)

	return {
		'encoding': 'utf-8',

		'formats': {
			'library': 'js',
			'fragment': 'js',
		},

		'reductions': {
			'library': {
				'interface': web.__name__ + '.javascript_uglify',
				'type': 'linker',
				'name': jscname,
				'command': str(jsc),
			},
		},

		'transformations': {
			'javascript': {
				'interface': libconstruct.__name__ + '.transparent',
				'type': 'transparent',
				'command': '/bin/cp',
			},
		}
	}

def css_subject(paths):
	"""
	Initialize the CSS subject for CSS compilation.
	"""
	css_combine = select(paths, ['cleancss', 'cat'], ('cleancss', 'cat',))
	cssname, cssc = css_combine

	css = {
		'encoding': 'utf-8',

		'formats': {
			'library': 'css',
		},

		'reductions': {
			'library': {
				'interface': web.__name__ + '.css_cleancss',
				'type': 'minify',
				'name': cssname,
				'command': str(cssc),
			},
		},

		'transformations': {
			'css': {
				'interface': libconstruct.__name__ + '.transparent',
				'type': 'transparent',
				'command': '/bin/cp',
			},
		}
	}

	less = select(paths, ['lessc'], ('lessc',))
	if less is not None:
		lessname, lessc = less
		css['transformations'].update({
			'less': {
				'interface': web.__name__ + '.lessc',
				'type': 'compiler',
				'name': lessname,
				'command': str(lessc),
			},
		})

	return css

def xml_subject(paths):
	"""
	Construct the subject for XML files.
	"""
	xmlname, xmlc = select(paths, ['xmllint'], ('xmllint',))

	xml = {
		'encoding': 'ascii',

		'formats': {
			'executable': 'xml',
			'library': 'xml',
		},

		'reductions': {
			'executable': {
				'interface': web.__name__ + '.xinclude',
				'type': 'xinclude',
				'name': xmlname,
				'command': str(xmlc),
				'redirect': 'stdout',
				'root': 'root.xml',
			},

			'library': {
				'interface': web.__name__ + '.xinclude',
				'type': 'xinclude',
				'name': xmlname,
				'command': str(xmlc),
				'redirect': 'stdout',
				'root': 'root.xml',
			},
		},

		'transformations': {
			'xml': {
				'interface': libconstruct.__name__ + '.transparent',
				'type': 'transparent',
				'command': '/bin/cp',
			},
		}
	}

	return xml

def resource_subject(paths):
	"""
	Initialize a (libconstruct:subject)`resource` subject for inclusion in a context.
	"""
	subject = {
		'formats': {
			'library': 'octets',
		},

		'reductions': {
			'library': {
				'interface': libconstruct.__name__ + '.inspect_link_editor',
				'command': 'fault.development.bin.il',
				'method': 'python',
				'redirect': 'stdout',
			},
		},

		'transformations': {
			None: {
				'interface': libconstruct.__name__ + '.transparent',
				'type': 'transparent',
				'command': '/bin/cp',
			},
		}
	}

	return subject

def inspect(ctx, paths):
	"""
	Initialize a (libconstruct:context)`inspect` context.
	"""
	iempty = {
		'command': 'fault.development.bin.empty_introspection',
		'interface': libconstruct.__name__ + '.empty',
		'method': 'python',
		'redirect': 'stdout',
	}
	il = {
		'interface': libconstruct.__name__ + '.inspect_link_editor',
		'command': 'fault.development.bin.il',
		'method': 'python',
		'redirect': 'stdout',
	}
	formats = {
		'library': 'xml',
		'executable': 'xml',
		'extension': 'xml',
		'fragment': 'xml',
		None: 'xml',
	}

	unsupported = {
		'formats': formats,
		'reductions': {
			'library': il,
			'executable': il,
			'extension': il,
			'fragmnt': il,
			None: il,
		},

		'transformations': {
			None: iempty,
			'javascript': iempty,
			'css': iempty,
			'less': iempty,
		},
	}

	core = {
		'javascript': unsupported,
		'xml': unsupported,
		'css': unsupported,
		'resource': unsupported,

		'system': {
			'formats': formats,
			'platform': 'xml-inspect-' + sys.platform,
			'reductions': {
				None: {
					'interface': libconstruct.__name__ + '.inspect_link_editor',
					'command': 'fault.development.bin.il',
					'method': 'python',
					'redirect': 'stdout',
				},
			},
			'transformations': {
				None: {
					'command': 'fault.development.bin.empty_introspection',
					'interface': libconstruct.__name__ + '.empty',
					'method': 'python',
					'redirect': 'stdout',
				},
				'objective-c': {
					'command': 'fault.llvm.bin.inspect',
					'interface': libconstruct.__name__ + '.compiler_collection',
					'method': 'python',
					'redirect': 'stdout',
				},
				'c++': {
					'command': 'fault.llvm.bin.inspect',
					'interface': libconstruct.__name__ + '.compiler_collection',
					'method': 'python',
					'redirect': 'stdout',
				},
				'c': {
					'command': 'fault.llvm.bin.inspect',
					'interface': libconstruct.__name__ + '.compiler_collection',
					'method': 'python',
					'redirect': 'stdout',
				},
			}
		}
	}

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
	rolefile.store(xml)

def host_system_subject(paths):
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
	version = version_info.strip()
	version_info = version.split('.', 3)

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

	# First field of the target string.
	arch = target[:target.find('-')]
	arch_alt = arch.replace('_', '-')

	cclib = compiler_libraries(ccname, ccprefix, '.'.join(version_info), cc, target)

	if ccname == 'gcc':
		profile_lib = cclib / 'libgcov.a'
		builtins = cclib / 'libgcc.a'
	elif ccname == 'clang':
		files = cclib.subnodes()[1]
		profile_libs = [x for x in files if 'profile' in x.identifier]

		if len(profile_libs) == 1:
			profile_lib = profile_libs[0]
		else:
			# Scan for library with matching architecture.
			for x in profile_libs:
				x = str(x)
				if arch in x or arch_alt in x:
					profile_lib = x
					break
			else:
				profile_lib = None

		if platform == 'darwin':
			builtins = str(cclib / 'libclang_rt.osx.a')
		else:
			# Similar to profile, scan for matching arch.
			cclibs = [x for x in files if 'builtins' in x.identifier]

			if len(cclibs) == 1:
				builtins = str(cclibs[0])
			else:
				# Scan for library with matching architecture.
				for x in cclibs:
					x = str(x)
					if arch in x or arch_alt in x:
						builtins = x
						break
				else:
					# clang, but no libclang_rt.
					builtins = '-lcompiler_rt.a'

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
	system = {
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
				'libraries': str(cclib),
				'version': tuple(map(int, version_info)),
				'release': release,
				'command': str(cc),
				'defaults': {},
				'resources': {
					'profile': str(profile_lib),
					'builtins': str(builtins),
				},
			},
		},
	}

	if platform == 'darwin':
		system['objects']['executable'] = {
			'pie': [
				prepare((found.get('crt1.o'), found.get('crti.o'), found.get('crtbeginS.o')),),
				prepare((found.get('crtendS.o'), found.get('crtn.o')),),
			],
		}
	else:
		# FreeBSD and many Linux systems.
		system['objects']['executable'] = {
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

	return system

def host(ctx, paths):
	"""
	Initialize a (libconstruct:context)`host` context.
	"""
	core = {
		'javascript': javascript_subject(paths),
		'css': css_subject(paths),
		'xml': xml_subject(paths),
		'system': host_system_subject(paths),
		'resource': resource_subject(paths),
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
	rolefile.store(xml)

def web_context(ctx, paths):
	# default command
	webcc = select(paths, ['emcc'], web_compiler_collection_preference)
	if webcc is None:
		return None
	ccname, cc = webcc

	# Execution method for targets.
	node = select(paths, ['emcc'], web_compiler_collection_preference)
	if node is None:
		return None
	node_name, node_c = node

	# Extract the default target from the compiler.
	target = 'js-web'

	# First field of the target string.
	arch = target[:target.find('-')]
	arch_alt = arch.replace('_', '-')

	libdirs = []

	core = {
		'javascript': javascript_subject(paths),
		'css': css_subject(paths),
		'xml': xml_subject(paths),
		'resource': resource_subject(paths),

		'system': {
			# subject data
			'platform': target,

			'reference-types': {'weak', 'lazy', 'upward', 'default'},

			# Formats to build for targets.
			# Fragments inherit the code type.
			'formats': {
				'executable': 'emscripten',
				'library': 'emscripten',
				'extension': 'emscripten',
			},

			# objects used to support the construction of system targets
			# The split (prefix objects and suffix objects) is used to support
			# linkers where the positioning of the parameters is significant.
			'objects': {
				'executable': {
					'emscripten': [],
				},
				'library': {
					'emscripten': [],
				},
				'extension': {
					'emscripten': [],
				},
				# fragments do not have requirements.
				'fragment': None,
			},

			# subject interfaces.
			'reductions': {
				None: {
					'interface': libconstruct.__name__ + '.web_link_editor',
					'type': 'linker',
					'name': 'emcc',
					'command': str(cc),
					'defaults': {},
				},
			},

			'transformations': {
				None: {
					'interface': libconstruct.__name__ + '.web_compiler_collection',
					'type': 'collection',
					'name': 'emcc',
					'command': str(cc),
					'implementation': 'emscripten',
					'libraries': [],
					'version': None,
					'release': None,
					'defaults': {},
					'resources': {
						'profile': None,
						'builtins': None
					},
				},
			},
		}
	}

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
	rolefile.store(xml)

def main(name, args, paths=None):
	global libroutes
	import os

	if args:
		libconstruct_dir, = args
	else:
		libconstruct_dir = libconstruct.root_context_directory()

	if paths is None:
		paths = libprobe.environ_paths()

	host(init(libconstruct_dir / 'host'), paths)
	inspect(init(libconstruct_dir / 'inspect'), paths)
	web_context(init(libconstruct_dir / 'web'), paths)

if __name__ == '__main__':
	import sys
	main(sys.argv[0], sys.argv[1:])
