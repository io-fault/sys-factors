"""
# Initialize a Construction Context for processing factors into a form usable by a system.
"""
import os
import sys
import functools
import subprocess

from fault.routes import library as libroutes
from fault.xml import library as libxml
from fault.system import library as libsys
from fault.system import libfactor

from .. import probe
from .. import cc
from .. import web

from itertools import product
from itertools import chain
chain = chain.from_iterable

javascript_combiners_preference = ['uglifyjs', 'cat']
compiler_collections = {
	'clang': (
		'c', 'c++',
		'objective-c', 'objective-c++',
		'fortran', 'ada', # via dragonegg
	),
	'gcc': (
		'c', 'c++', 'objective-c',
		'fortran', 'ada', 'java',
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

compiler_collection_preference = ['clang', 'gcc', 'icc',]

linkers = {
	'lld': (
		'objects',
	),
	'ld': (
		'objects',
	),
}
linker_preference = ('lld', 'ld')

environment = {
	'CC': 'compiler_collections',
	'LINKER': 'system_linkers',
	'STRIP': 'strip',
	'OBJCOPY': 'objcopy',
}

pyrex_compilers = {
	'cython',
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
	# Python partial = source file

	from ...adapters.python.bin import compile
	pyexe = select(paths, ['python3', 'python3.4', 'python3.5', 'python3.6', 'python3.7'], ['python3'])
	pyname, pycommand = pyexe

	return {
		'target-file-extensions': {},

		'formats': {
			'library': 'pyc',
		},

		'transformations': {
			'python': {
				'method': 'internal',
				'interface': compile.__name__ + '.function_bytecode_compiler',
				'name': 'pyc',
				'command': __package__ + '.compile',
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
		'interface': cc.__name__ + '.transparent',
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
				'interface': cc.__name__ + '.concatenation',
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
			'partial': 'js',
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
				'interface': cc.__name__ + '.transparent',
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
			'partial': '.xml',
			'library': '.d',
		},

		'formats': {
			'executable': 'xml',
			'partial': 'xml',
			'library': 'xml',
		},

		'integrations': {
			'executable': {
				'interface': web.__name__ + '.xml_combine',
				'name': 'integrate',
				'command': __package__ + '.xml',
				'root': 'root.xml',
				'method': 'python',
			},

			'partial': {
				'interface': web.__name__ + '.xml_combine',
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
				'interface': cc.__name__ + '.standard_io',
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
			'partial': 'octets',
		},

		'transformations': {
			None: {
				'interface': cc.__name__ + '.transparent',
				'type': 'transparent',
				'command': '/bin/cp',
			},
		}
	}

	return mech

def resource_domain(paths):
	"""
	# Initialize a (factor/type)`resource` subject for inclusion in a context.
	"""

	mech = {
		'target-file-extensions': {None:''}, # Resources manage their own.

		'formats': {
			'library': 'octets',
		},

		'transformations': {
			None: {
				'interface': cc.__name__ + '.transparent',
				'type': 'transparent',
				'command': '/bin/cp',
			},
			'uri': {
				'interface': cc.__name__ + '.transparent',
				'method': 'python',
				'command': __package__ + '.stream',
				'redirect': 'stdout',
			}
		}
	}

	return mech

def delineation(reqs, ctx, paths):
	"""
	# Initialize a `fragments` context for managing fragment extraction.
	"""

	iempty = {
		'command': 'kit.factors.bin.delineate',
		'interface': cc.__name__ + '.empty',
		'method': 'python',
		'redirect': 'stdout',
	}

	formats = {
		'library': 'xml',
		'executable': 'xml',
		'extension': 'xml',
		'partial': 'xml',
		None: 'xml',
	}

	# For XML, the documents are embedded.
	xml_domain = {
		'formats': formats,
		'target-file-extensions': {None:'.xml'},
		'transformations': {
			None: {
				'command': 'fault.xml.bin.delineate',
				'interface': cc.__name__ + '.standard_out',
				'method': 'python',
				'redirect': 'stdout',
			},

			'txt': {
				'command': 'fault.text.bin.delineate',
				'interface': cc.__name__ + '.standard_out',
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
				'command': 'kit.factors.bin.delineate',
				'interface': cc.__name__ + '.standard_out',
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
				'command': 'kit.factors.bin.delineate',
				'interface': cc.__name__ + '.standard_out',
				'method': 'python',
				'redirect': 'stdout',
			},
		},
	}

	unsupported = {
		'target-file-extensions': {None:'.void'},
		'formats': formats,
		'transformations': {None: iempty},
	}

	python = {
		'target-file-extensions': {None:'.xml'},
		'formats': formats,
		'transformations': {None: iempty}
	}

	system = {
		'formats': formats,
		'target-file-extensions': {None:'.xml'},
		'platform': 'xml-inspect-' + sys.platform,
		'transformations': {None: iempty}
	}

	core = {
		'[trap]': unsupported,
		'factor': python,

		'xml': xml_domain,
		'system': system,
		'source': system,
		'javascript': js_domain,
		'css': css_domain,
	}

	S = libxml.Serialization()
	D = S.switch('data:')
	xml = b''.join(
		S.root('mechanism',
			libxml.Data.serialize(D, core),
			('name', 'fragments'),
			('xmlns', 'http://fault.io/xml/dev/fpi'),
			('xmlns:data', 'http://fault.io/xml/data'),
		),
	)

	corefile = ctx / 'core.xml'
	corefile.store(xml)

	return corefile

def host_system_domain(intention, reqs, paths):
	target_file_extensions = {
		'executable': '.exe',
		'library': '.so',
		'extension': '.so',
		'partial': '.fo',
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
		cc_route = libroutes.File.from_path(reqs['cc'])
		ccname = cc_route.identifier
	elif 'CC' in os.environ:
		cc_route = libroutes.File.from_absolute(os.environ['CC'])
		ccname = cc_route.identifier
	else:
		ccname, cc_route = select(paths,
			compiler_collections, compiler_collection_preference)
	ldname, ld = select(paths, linkers, linker_pref)

	bindir = cc_route.container
	ccprefix = bindir.container
	profile_lib = None

	# gather compiler information.
	p = subprocess.Popen([str(cc_route), '--version'],
		stderr=subprocess.STDOUT, stdout=subprocess.PIPE, stdin=None)
	data = p.communicate(None)[0].decode('utf-8').split('\n')

	# Analyze the library search directories.
	# Primarily interested in finding the crt*.o files for linkage.
	p = subprocess.Popen([str(cc_route), '-print-search-dirs'],
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

	cclib = compiler_libraries(ccname, ccprefix, '.'.join(version_info), cc_route, target)
	builtins = None
	if cclib is None:
		cclib = libroutes.File.from_relative(root, search_dirs_data['libraries'][0])
		cclib = cclib / 'lib' / platform

	if ccname == 'gcc':
		profile_lib = cclib / 'libgcov.a'
		builtins = cclib / 'libgcc.a'
	elif ccname == 'clang' and cclib is not None:
		files = cclib.subnodes()[1]

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

	libdirs = [
		libroutes.File.from_relative(root, str(x).strip('/'))
		for x in search_dirs_data['libraries']
	]
	libdirs.extend(map(libroutes.File.from_absolute,
		('/lib', '/usr/lib',))) # Make sure likely directories are included.

	# scan for system objects (crt1.o, crt0.o, etc)
	found, missing = probe.search(libdirs, runtime_objects)
	prepare = lambda x: tuple(map(str, [y for y in x if y]))

	if ccname == 'clang':
		xfname = 'tool:llvm-clang'
	elif ccname == 'gcc':
		xfname = 'tool:gnu-gcc'
	else:
		xfname = 'tool:cc'

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
			# partials do not have requirements.
			'partial': None,
		},

		# subject interfaces.
		'integrations': {
			None: {
				'interface': cc.__name__ + '.link_editor',
				'type': 'linker',
				'name': ldname,
				'command': str(ld),
				'defaults': {},
			}
		},

		'transformations': {
			xfname: {
				'interface': cc.__name__ + '.compiler_collection',
				'type': 'collection',
				'name': ccname,
				'implementation': cctype,
				'libraries': str(cclib),
				'version': tuple(map(int, version_info)),
				'release': release,
				'command': str(cc_route),
				'defaults': {},
				'options': [],
				'resources': {
					'builtins': str(builtins) if builtins else None,
				},
				'feature-control': {
					'c++' : {
						'exceptions': ('-fexceptions', '-fno-exceptions'),
						'rtti': ('-frtti', '-fno-rtti'),
					},
				}
			},
			# Default compiler.
			None: {
				'inherit': xfname,
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
			# PDC or PIE based executables.
			# PDC does not mean that the library is a (completely) statically linked binary.
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

	'injections': 'Debugging intention with support for injections for comprehensive testing',
	'instruments': 'Test intention with profiling and coverage collection enabled',
	'fragments': 'Context used to delineate fragments from source files',
}

def designate(corefile, intent, filename):
	abstract = common_intentions[intent]
	ctx = corefile.container
	S = libxml.Serialization()
	D = S.switch('data:')

	empty = {}
	ctxfile = ctx / filename

	xml = b''.join(
		S.root('context', chain((
				S.element('xi:include',
					(),
					('href', corefile.identifier),
				),
				S.element('mechanism',
					libxml.Data.serialize(D, empty),
				),
			)),
			('xmlns', 'http://fault.io/xml/dev/fpi'),
			('xmlns:data', 'http://fault.io/xml/data'),
			('xmlns:xi', libxml.namespaces['xinclude']),
		)
	)
	ctxfile.store(xml)

def store_mechanisms(route, data, name=None, intention=None):
	"""
	# Serialize the mechanisms' data.
	"""
	S = libxml.Serialization()
	D = S.switch('data:')

	xml = b''.join(
		S.root('context',
			S.element('mechanism',
				libxml.Data.serialize(D, data),
				('name', name),
			),
			('xmlns', 'http://fault.io/xml/dev/fpi'),
			('xmlns:data', 'http://fault.io/xml/data'),
			('xmlns:xi', libxml.namespaces['xinclude']),
		)
	)

	route.store(xml)
	return len(xml)

def static(reqs, ctx, paths):
	"""
	# Invariant factor processing.
	"""
	data = {
		'source': source_domain(paths),
		'resource': resource_domain(paths),
		'javascript': javascript_domain(paths),
		'css': css_domain(paths),
		'xml': xml_domain(paths),
	}

	store_mechanisms(ctx/'static.xml', data, name='static')

def empty(target, name):
	store_mechanisms(target, {}, name=name)

def host(intention, reqs, ctx, paths):
	"""
	# Initialize a construction context for host targets.
	"""

	core = {
		'system': host_system_domain(intention, reqs, paths),
		# Move to static.
		'factor': python_bytecode_domain(paths),
	}

	S = libxml.Serialization()
	D = S.switch('data:')
	xml = b''.join(
		S.element('mechanism',
			libxml.Data.serialize(D, core),
			('name', 'host'),
			('xmlns', 'http://fault.io/xml/dev/fpi'),
			('xmlns:data', 'http://fault.io/xml/data'),
		),
	)

	corefile = ctx / 'core.xml'
	corefile.store(xml)

	return corefile

prefix = b"""
import sys
import os
import os.path
factors = os.environ.get('FACTORS')
if factors and factors != fpath:
	fpath = fpath + ':' + factors
ctx_path = os.path.realpath(os.path.dirname(sys.argv[0]))
ctx_lib = os.path.join(ctx_path, 'lib', 'python')
os.environ['CONTEXT'] = ctx_path
dev_bin = %s
""" %(repr(__package__).encode('utf-8'),)

ep_template = prefix + b"""
os.environ['PYTHONPATH'] = ctx_lib + ':' + fpath if fpath else ctx_lib
os.execv(sys.executable, [
		sys.executable, '-m', %s,
		'context', ctx_path,
	] + sys.argv[1:]
)
"""

def sysconfig_python_parameters():
	"""
	# Collect the python reference parameter from the &sysconfig module.
	"""
	import sysconfig

	version = '.'.join(map(str, sys.version_info[:2]))
	abi = sys.abiflags
	triplet = \
		sys.implementation.name + \
		'-' + version.replace('.', '') + abi + \
		'-' + sys.platform

	libsuffix = version + abi
	libname = 'python' + libsuffix

	incdir = sysconfig.get_config_var('INCLUDEPY')
	libdir = sysconfig.get_config_var('LIBDIR')

	return {
		'identifier': triplet,

		'implementation': sys.implementation.name,
		'version': version,
		'abi': abi,

		'factors': {
			'source': {
				'library': {
					str(incdir): {None},
				}
			},
			'system': {
				'library': {
					str(libdir): {libname},
				}
			},
		}
	}

def materialize_support_project(directory, name):
	from fault.text import bin as tmodule
	from .. import templates

	status = os.spawnv(os.P_WAIT, sys.executable, [
		sys.executable, '-m', tmodule.__name__ + '.ifst',
		str(directory), templates.__name__, 'context', name
	])
	(directory / '__init__.py').init('file')
	(directory / 'extensions' / '__init__.py').init('file')

	return status

def context(route, intention, reference, parameters):
	ctx = route
	mechdir = ctx / 'mechanisms'
	lib = ctx / 'lib'
	work = ctx / 'work'
	params = ctx / 'parameters'
	pylib = lib / 'python'

	for x in mechdir, lib, work, pylib:
		x.init('directory')

	# Initialize entry point for context.
	initial = __package__.split('.')[0]
	kit = sys.modules[initial]
	pypath = os.path.dirname(os.path.dirname(kit.__file__))
	pypath = '\nfpath = ' + repr(pypath)

	dev = (ctx / 'execute')
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

	# Initialize context/parameters and store the Python parameter.
	params.init('directory')

	if reference is not None:
		support = str(reference)
	else:
		support = ''

	ctxparams = (params / 'context.xml')
	ctxparams.init('file')
	xml = libxml.Serialization()
	x = cc.Parameters.serialize_parameters(xml,
		'http://protocol.fault.io/factor/context',
		{
			'support': support,
			'name': 'host',
			'intention': intention,
			# incorporate namespace
			'incorporation': parameters.get('incorporation'),
			# cache slot for incorporated targets
			'slot': parameters.get('slot', 'factor'),
			'optimizations': {
				'time': 1 if intention == 'optimal' else 0,
				'debug': 1 if intention in {'debug','injections','instruments'} else 0,
				'size': 0,
				'power': 0,
			},
		},
	)
	ctxparams.store(b''.join(x))

	python = (params / 'python.xml')
	python.init('file')
	xml = libxml.Serialization()
	x = cc.Parameters.serialize_parameters(xml,
		'http://protocol.fault.io/factor/python',
		sysconfig_python_parameters()
	)
	python.store(b''.join(x))

	paths = probe.environ_paths()

	if intention == 'fragments':
		corefile = delineation(parameters, mechdir, paths)
		designate(corefile, intention, 'intent.xml')
		empty(ctx/'mechanisms'/'static.xml', 'static')
	else:
		corefile = host(intention, parameters, mechdir, paths)
		designate(corefile, intention, 'intent.xml')
		static(parameters, mechdir, paths)

	materialize_support_project(pylib / 'f_intention', 'intention')

def main(inv):
	refctx = None
	intention, target, *args = inv.args
	reqs = dict(zip(args[0::2], args[1::2]))

	if 'CONTEXT' in os.environ:
		refctx = libroutes.File.from_absolute(os.environ['CONTEXT'])

	target = libroutes.File.from_path(target)
	context(target, intention, refctx, reqs)
	return inv.exit(0)

if __name__ == '__main__':
	libsys.control(main, libsys.Invocation.system())
