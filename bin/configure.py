"""
Configure the initialization of the construction context.
"""
import sys
import functools

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

compiler_collection_preference = ('clang', 'gcc', 'cl.exe')

linkers = {
	'lld': (
		'objects',
	),
	'ld': (
		'objects',
	),
}

linker_preference = ('lld', 'ld')

haskell_compilers = {
	'ghc': ('haskell',),
}

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
	ccname, cc = select(paths, compiler_collections, compiler_collection_preference)
	ldname, ld = select(paths, linkers, linker_preference)

	core = {
		'system': {
			None: {
				'interface': libconstruct.__name__ + '.link_editor',
				'type': 'linker',
				'name': ldname,
				'command': str(ld),
				'defaults': {},
			},
			'compiler': {
				'interface': libconstruct.__name__ + '.compiler_collection',
				'type': 'collection',
				'name': ccname,
				'command': str(cc),
				'defaults': {},
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

	with rolefile.open('wb') as f:
		f.write(xml)

	# Initialize lib directory for context libraries.
	ctxlib = ctx / 'lib'
	ctxlib.init('directory')

if __name__ == '__main__':
	import sys
	main(sys.argv[0], sys.argv[1:])
