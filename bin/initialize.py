"""
# Initialize a Construction Context for preparing factors for use.
"""
import os
import sys
import functools
import subprocess

from ...routes import library as libroutes
from ...xml import library as libxml
from ...system import library as libsys
from ...system import libfactor
from .. import probe
from .. import library as libdev
from .. import web

from itertools import product
from itertools import chain
chain = chain.from_iterable

javascript_combiners_preference = ['uglifyjs', 'cat']
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
		'c', 'c++',
		'objective-c', 'objective-c++',
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

compiler_collection_preference = ['clang', 'gcc', 'icc', 'cl.exe']

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

def debug_isolate(self, target):
	dtarget = target + '.dSYM'
	return dtarget, [
		('dsymutil', target, '-o', dtarget)
	]

def debug_isolate(self, target):
	"""
	# Isolate debugging information from the target.
	"""
	debugfile = target + '.debug'

	return [
		(objcopy, '--only-keep-debug', target, debugfile),
		(strip, '--strip-debug', '--strip-unneeded', target),
		(objcopy, '--add-gnu-debuglink', target, debug),
	]

def select(paths, possibilities, preferences):
	"""
	# Select a file from the given &paths using the &possibilities and &preferences
	# to identify the most desired.
	"""

	# Override for particular version
	possible = set(possibilities)

	found, missing = probe.search(paths, tuple(possible))
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

	'crtbeginT.o', # Statically linked executables.
	'crtend.o',

	'crtbeginS.o', # Shared libraries.
	'crtendS.o',

	'crti.o',
	'crtn.o',
])

def compiler_libraries(compiler, prefix, version, executable, target):
	"""
	# Attempt to select the compiler libraries directory containing compiler support
	# libraries for profiling, sanity, and runtime.
	"""
	if compiler == 'clang':
		lib = prefix / 'lib' / 'clang' / version / 'lib'
		syslib = lib / platform # Naturally, not always consistent.
		if syslib.exists():
			return syslib
		syslib = prefix / 'lib' / platform
		if syslib.exists():
			return syslib
	elif compiler == 'gcc':
		return prefix / 'lib' / 'gcc' / target / version
	else:
		pass

def python_bytecode_domain(paths):
	"""
	# Constructs the subject for building Python bytecode for a host context.

	# Currently, only builds subject for the executing Python.

	# ! DEVELOPMENT: Features
		# Must provide a means for compiling with versions of
		# Python aside from the one that is running. A reasonable
		# possibility is constructing the the `-c` command.
	"""
	# Python library = module with preprocessed sources
	# Python executable = python source executed in __main__
	# Python extension = maybe python source executed in a library?
	# Python fragment = source file

	pyexe = select(paths, ['python3', 'python3.4', 'python3.5', 'python3.6'], ['python3'])
	pyname, pycommand = pyexe

	return {
		'target-file-extensions': {},

		'formats': {
			'library': 'pyc',
		},

		'transformations': {
			'python': {
				'method': 'internal',
				'interface': libdev.__name__ + '.local_bytecode_compiler',
				'name': 'pyc',
				'command': __package__ + '.pyc',
			},
		}
	}

def javascript_domain(paths):
	"""
	# Initialize the javascript domain for JavaScript file compilation.

	# This primarily means "minification" and mere concatenation, but languages
	# targeting JavaScript can be added.
	"""

	jscat = select(paths, ['uglifyjs', 'cat'], javascript_combiners_preference)
	if jscat is None:
		return None
	jscname, jsc = jscat

	# Currently a transparent copy for raw javascript.
	transforms = {
		'interface': libdev.__name__ + '.transparent',
		'type': 'transparent',
		'command': '/bin/cp',
	}

	if jscname == 'uglifyjs':
		ints = {
			'library': {
				'interface': web.__name__ + '.javascript_uglify',
				'type': 'linker',
				'name': jscname,
				'command': str(jsc),
			},
		}
	else:
		ints = {
			'library': {
				'interface': libdev.__name__ + '.concatenation',
				'type': 'linker',
				'name': 'cat',
				'command': str(jsc),
			}
		}

	return {
		'encoding': 'utf-8',
		'target-file-extensions': {None:'.js'},

		'formats': {
			'executable': 'js',
			'library': 'js',
			'fragment': 'js',
		},

		'integrations': ints,

		'transformations': {
			'javascript': transforms
		}
	}

def css_domain(paths):
	"""
	# Initialize the CSS subject for CSS compilation.
	"""

	css_combine = select(paths, ['cleancss', 'cat'], ('cleancss', 'cat',))
	if css_combine is None:
		return None
	cssname, cssc = css_combine

	css = {
		'encoding': 'utf-8',
		'target-file-extensions': {None:'.css'},

		'formats': {
			'library': 'css',
		},

		'integrations': {
			'library': {
				'interface': web.__name__ + '.css_cleancss',
				'type': 'minify',
				'name': cssname,
				'command': str(cssc),
			},
		},

		'transformations': {
			'css': {
				'interface': libdev.__name__ + '.transparent',
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

def xml_domain(paths):
	"""
	# Construct the subject for XML files.
	"""

	xml = {
		'encoding': 'ascii',
		'target-file-extensions': {
			'executable': '.xml',
			'fragment': '.xml',
			'library': '.d',
		},

		'formats': {
			'executable': 'xml',
			'fragment': 'xml',
			'library': 'xml',
		},

		'integrations': {
			'executable': {
				'interface': web.__name__ + '.xml',
				'name': 'integrate',
				'command': __package__ + '.xml',
				'root': 'root.xml',
				'method': 'python',
			},

			'fragment': {
				'interface': web.__name__ + '.xml',
				'name': 'integrate',
				'command': __package__ + '.xml',
				'root': 'root.xml',
				'method': 'python',
			},

			'library': {
				'interface': web.__name__ + '.xml_link',
				'name': 'integrate',
				'command': 'fault.xml.bin.ld',
				'method': 'python',
			},
		},

		'transformations': {
			'xml': {
				'interface': web.__name__ + '.xml',
				'name': 'transform',
				'method': 'python',
				'command': __package__ + '.xml',
			},

			'txt': {
				'interface': libdev.__name__ + '.standard_io',
				'name': 'transform',
				'method': 'python',
				'command': 'fault.text.bin.xml',
				'redirect': 'io',
			},
		}
	}

	return xml

def source_domain(paths):
	"""
	# Initialize (factor/domain)`resource` for inclusion in a context.
	"""

	mech = {
		'target-file-extensions': {None:''},

		'formats': {
			'executable': 'octets',
			'library': 'octets',
			'extension': 'octets',
			'fragment': 'octets',
		},

		'transformations': {
			None: {
				'interface': libdev.__name__ + '.transparent',
				'type': 'transparent',
				'command': '/bin/cp',
			},
		}
	}

	return mech

def resource_domain(paths):
	"""
	# Initialize a (ctx:ftype)`resource` subject for inclusion in a context.
	"""

	mech = {
		'target-file-extensions': {None:''}, # Resources manage their own.

		'formats': {
			'library': 'octets',
		},

		'transformations': {
			None: {
				'interface': libdev.__name__ + '.transparent',
				'type': 'transparent',
				'command': '/bin/cp',
			},
			'uri': {
				'interface': libdev.__name__ + '.transparent',
				'method': 'python',
				'command': __package__ + '.stream',
				'redirect': 'stdout',
			}
		}
	}

	return mech

def inspect(reqs, ctx, paths):
	"""
	# Initialize an `inspect` context for managing delineation adaptions.
	"""

	iempty = {
		'command': 'fault.development.bin.delineate',
		'interface': libdev.__name__ + '.empty',
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

	# For XML, the documents are embedded.
	xml_domain = {
		'formats': formats,
		'target-file-extensions': {None:'.xml'},
		'transformations': {
			None: {
				'command': 'fault.xml.bin.delineate',
				'interface': libdev.__name__ + '.standard_out',
				'method': 'python',
				'redirect': 'stdout',
			},

			'txt': {
				'command': 'fault.text.bin.delineate',
				'interface': libdev.__name__ + '.standard_out',
				'method': 'python',
				'redirect': 'stdout',
			},
		}
	}

	js_domain = {
		'formats': formats,
		'target-file-extensions': {None:'.xml'},
		'transformations': {
			None: {
				'command': 'fault.development.bin.delineate',
				'interface': libdev.__name__ + '.standard_out',
				'method': 'python',
				'redirect': 'stdout',
			},
		},
	}

	css_domain = {
		'formats': formats,
		'target-file-extensions': {None:'.xml'},
		'transformations': {
			None: {
				'command': 'fault.development.bin.delineate',
				'interface': libdev.__name__ + '.standard_out',
				'method': 'python',
				'redirect': 'stdout',
			},
		},
	}

	unsupported = {
		'target-file-extensions': {None:'.void'},
		'formats': formats,
		'transformations': {
			None: iempty,
		},
	}

	python = {
		'target-file-extensions': {None:'.xml'},
		'formats': formats,

		'transformations': {
			'python': {
				'command': 'fragments.python.bin.delineate',
				'interface': libdev.__name__ + '.package_module_parameter',
				'method': 'python',
				'name': 'delineate-python-source',
				'redirect': 'stdout'
			},
		}
	}

	llvm = {
		'command': 'fragments.llvm.bin.delineate',
		'interface': libdev.__name__ + '.compiler_collection',
		'method': 'python',
		'redirect': 'stdout',
	}

	system = {
		'formats': formats,
		'target-file-extensions': {None:'.xml'},
		'platform': 'xml-inspect-' + sys.platform,
		'transformations': {
			None: iempty,
			'objective-c': llvm,
			'c++[rtti exceptions]': llvm,
			'c++': llvm,
			'c': llvm,
			'c-header': llvm,
			'c++-header': llvm,
		}
	}

	core = {
		'[trap]': unsupported,
		'bytecode.python': python,

		'xml': xml_domain,
		'system': system,
		'source': system,
		'javascript': js_domain,
		'css': css_domain,
	}

	S = libxml.Serialization()
	D = S.switch('data:')
	xml = b''.join(
		S.root('context',
			libxml.Data.serialize(D, core),
			('name', 'inspect'),
			('xmlns', 'http://fault.io/xml/dev/fpi'),
			('xmlns:data', 'http://fault.io/xml/data'),
		),
	)

	corefile = ctx / 'core.xml'
	corefile.store(xml)

	intentions(corefile)

def host_system_domain(reqs, paths):
	target_file_extensions = {
		'executable': '.exe',
		'library': '.so',
		'extension': '.so',
		'fragment': '.fo',
		None: '.so',
	}
	root = libroutes.File.from_absolute('/')

	if platform in {'darwin', 'macos'}:
		target_file_extensions['library'] = '.dylib'
		target_file_extensions['extension'] = '.dylib'
		linker_pref = ('ld', 'lld')
	elif platform in {'win', 'msw'}:
		target_file_extensions['library'] = '.dll'
		target_file_extensions['extension'] = '.dll'
		linker_pref = linker_preference
	else:
		linker_pref = linker_preference

	# default command
	if 'cc' in reqs:
		cc = libroutes.File.from_path(reqs['cc'])
		ccname = cc.identifier
	elif 'CC' in os.environ:
		cc = libroutes.File.from_absolute(os.environ['CC'])
		ccname = cc.identifier
	else:
		ccname, cc = select(paths,
			compiler_collections, compiler_collection_preference)
	ldname, ld = select(paths, linkers, linker_pref)

	bindir = cc.container
	ccprefix = bindir.container
	profile_lib = None

	# gather compiler information.
	p = subprocess.Popen([str(cc), '--version'],
		stderr=subprocess.STDOUT, stdout=subprocess.PIPE, stdin=None)
	data = p.communicate(None)[0].decode('utf-8').split('\n')

	# Analyze the library search directories.
	# Primarily interested in finding the crt*.o files for linkage.
	p = subprocess.Popen([str(cc), '-print-search-dirs'],
		stderr=subprocess.STDOUT, stdout=subprocess.PIPE, stdin=None)
	search_dirs_data = p.communicate(None)[0].decode('utf-8').split('\n')
	search_dirs_data = [x.split(':', 1) for x in search_dirs_data if x]
	search_dirs_data = dict([
		(k.strip(' =:').lower(), list((x.strip(' =') for x in v.split(':'))))
		for k, v in search_dirs_data
	])

	version_line = data[0]
	cctype, version_spec = version_line.split(' version ')
	version_info, release = version_spec.split('(', 1)
	release = release.strip('()')
	version = version_info.strip()
	version_info = version.split('.', 3)

	if cctype == 'Apple LLVM' or 'clang' in ccname:
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
	h_archs = [arch, arch_alt, platform]
	if platform == 'darwin':
		h_archs.append('osx')
		h_archs.append('macos')

	cclib = compiler_libraries(ccname, ccprefix, '.'.join(version_info), cc, target)
	builtins = None
	if cclib is None:
		cclib = libroutes.File.from_relative(root, search_dirs_data['libraries'][0])
		cclib = cclib / 'lib' / platform

	if ccname == 'gcc':
		profile_lib = cclib / 'libgcov.a'
		builtins = cclib / 'libgcc.a'
	elif ccname == 'clang' and cclib is not None:
		files = cclib.subnodes()[1]
		profile_libs = [x for x in files if 'profile' in x.identifier]

		if len(profile_libs) == 1:
			# Presume target of interest.
			profile_lib = profile_libs[0]
		else:
			# Scan for library with matching architecture.
			for x, a in product(profile_libs, h_archs):
				if a in x.identifier:
					profile_lib = str(x)
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
				for x, a in product(cclibs, h_archs):
					if a in x.identifier:
						builtins = str(x)
						break
				else:
					# clang, but no libclang_rt.
					builtins = None

	libdirs = [libroutes.File.from_relative(root, str(x).strip('/')) for x in search_dirs_data['libraries']]
	libdirs.extend(map(libroutes.File.from_absolute,
		('/lib', '/usr/lib',))) # Make sure likely directories are included.

	# scan for system objects (crt1.o, crt0.o, etc)
	found, missing = probe.search(libdirs, runtime_objects)
	prepare = lambda x: tuple(map(str, [y for y in x if y]))
	system = {
		# domain data
		'platform': target,
		'architecture': arch,
		'target-file-extensions': target_file_extensions,
		'ignore-extensions': {'h', 'hh', 'hpp'},

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
		'integrations': {
			None: {
				'interface': libdev.__name__ + '.link_editor',
				'type': 'linker',
				'name': ldname,
				'command': str(ld),
				'defaults': {},
			}
		},

		'transformations': {
			None: {
				'interface': libdev.__name__ + '.compiler_collection',
				'type': 'collection',
				'name': ccname,
				'implementation': cctype,
				'libraries': str(cclib),
				'version': tuple(map(int, version_info)),
				'release': release,
				'command': str(cc),
				'defaults': {},
				'resources': {
					'profile': str(profile_lib) if profile_lib else None,
					'builtins': str(builtins) if builtins else None,
				},
			},

			# -fno-rtti -fno-exceptions
			'c++[rtti exceptions]': {
				'inherit': None,
				'language': 'c++',
				'options': (
					'-fno-exceptions',
					'-fno-rtti',
				)
			}
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

common_intentions = {
	'optimal': 'Subjective performance selection',
	'debug': 'Reduced optimizations and defines for emitting debugging information',

	'test': 'Debugging intention with support for injections for comprehensive testing',
	'metrics': 'Test intention with profiling and coverage collection enabled',

	'profiling': 'Raw profiling build for custom collections',
	'coverage': 'Raw coverage build for custom collections',
}

def intentions(corefile):
	ctx = corefile.container
	S = libxml.Serialization()
	D = S.switch('data:')

	empty = {}
	for x, abstract in common_intentions.items():
		ctxfile = ctx / (x + '.xml')

		xml = b''.join(
			S.root('libconstruct', chain((
					S.element('xi:include',
						(),
						('href', corefile.identifier),
					),
					S.element('context',
						libxml.Data.serialize(D, empty),
						('intention', x),
					),
				)),
				('xmlns', 'http://fault.io/xml/dev/fpi'),
				('xmlns:data', 'http://fault.io/xml/data'),
				('xmlns:xi', libxml.namespaces['xinclude']),
			)
		)
		ctxfile.store(xml)

def static(reqs, ctx, paths):
	"""
	# Platform independent processing.
	"""

	core = {
		'source': source_domain(paths),
		'resource': resource_domain(paths),
		'javascript': javascript_domain(paths),
		'css': css_domain(paths),
		'xml': xml_domain(paths),
	}

	import pprint
	pprint.pprint(core)

	S = libxml.Serialization()
	D = S.switch('data:')

	xml = b''.join(
		S.root('context',
			libxml.Data.serialize(D, core),
			('name', 'static'),
			('xmlns', 'http://fault.io/xml/dev/fpi'),
			('xmlns:data', 'http://fault.io/xml/data'),
		)
	)

	corefile = ctx / 'core.xml'
	corefile.store(xml)

	intentions(corefile)

def host(reqs, ctx, paths):
	"""
	# Initialize a (libdev:context)`host` context.
	"""

	core = {
		'system': host_system_domain(reqs, paths),
		# Move to static.
		'bytecode.python': python_bytecode_domain(paths),
	}

	import pprint
	pprint.pprint(core)

	S = libxml.Serialization()
	D = S.switch('data:')
	xml = b''.join(
		S.element('context',
			libxml.Data.serialize(D, core),
			('name', 'host'),
			('xmlns', 'http://fault.io/xml/dev/fpi'),
			('xmlns:data', 'http://fault.io/xml/data'),
		),
	)

	corefile = ctx / 'core.xml'
	corefile.store(xml)

	intentions(corefile)

def web_context(reqs, ctx, paths):
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
		'system': {
			# subject data
			'platform': target,
			'source.parameters': [
				('PRODUCT_ARCHITECTURE', target),
			],

			'target-file-extensions': {
				None: '.js',
				'fragment': '.bc',
			},

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
			'integrations': {
				None: {
					'interface': libdev.__name__ + '.web_link_editor',
					'type': 'linker',
					'name': 'emcc',
					'command': str(cc),
					'defaults': {},
				},
			},

			'transformations': {
				None: {
					'interface': libdev.__name__ + '.web_compiler_collection',
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
		S.root('context',
			libxml.Data.serialize(D, core),
			('name', 'web'),
			('xmlns', 'http://fault.io/xml/dev/fpi'),
			('xmlns:data', 'http://fault.io/xml/data'),
		),
	)

	corefile = ctx / 'core.xml'
	corefile.store(xml)

	intentions(corefile)

prefix = b"""
import sys
import os
import os.path
factors = os.environ.get('FACTORS')
if factors and factors != fpath:
	fpath = fpath + ':' + factors
ctx_path = os.path.realpath(os.path.dirname(sys.argv[0]))
os.environ['CONTEXT'] = ctx_path
dev_bin = %s
""" %(repr(__package__).encode('utf-8'),)

ep_template = prefix + b"""
os.environ['PYTHONPATH'] = fpath
os.execv(sys.executable, [
		sys.executable, '-m', %s,
		'context', ctx_path,
	] + sys.argv[1:]
)
"""

def main(inv):
	target, *args = inv.args
	reqs = dict(zip(args[0::2], args[1::2]))

	ctx = libroutes.File.from_path(target)
	mechdir = ctx / 'mechanisms'
	measures = ctx / 'measurements'
	lib = ctx / 'lib'
	work = ctx / 'work'

	for x in mechdir, measures, lib, work:
		x.init('directory')

	for x in 'host', 'static', 'inspect', 'web':
		(mechdir / x).init('directory')

	# Initialize entry point for context.
	initial = __package__.split('.')[0]
	fault = sys.modules[initial]
	pypath = os.path.dirname(os.path.dirname(fault.__file__))
	pypath = '\nfpath = ' + repr(pypath)

	dev = (ctx / 'develop')
	dev.init('file')
	src = ep_template % (
		repr(__package__ + '.interface').encode('utf-8'),
	)
	dev.store(b'#!' + sys.executable.encode('utf-8') + pypath.encode('utf-8') + src)
	os.chmod(str(dev), 0o744)

	cfg = (ctx / 'configure')
	cfg.init('file')
	src = ep_template % (
		repr(__package__ + '.configure').encode('utf-8'),
	)
	cfg.store(b'#!' + sys.executable.encode('utf-8') + pypath.encode('utf-8') + src)
	os.chmod(str(cfg), 0o744)

	paths = probe.environ_paths()
	host(reqs, mechdir / 'host', paths)
	static(reqs, mechdir / 'static', paths)
	inspect(reqs, mechdir / 'inspect', paths)
	web_context(reqs, mechdir / 'web', paths)

	# Initialze default scanner probes.
	sa = (ctx / 'scanner')
	probed = (sa / 'probes')
	from .. import probes
	pid = os.spawnv(os.P_WAIT, sys.executable, [sys.executable, '-m', probes.__name__, str(probed)])
	(probed / '__init__.py').init('file')

	sys.exit(0)

if __name__ == '__main__':
	libsys.control(main, libsys.Invocation.system())
