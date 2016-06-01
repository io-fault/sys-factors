"""
Configure the initialization of the construction context.
"""
import sys
import functools

from ...routes import library as libroutes
from ...xml import library as libxml
from .. import libprobe

system_linkers = {
	'ld': None,
	'lld': None,
	'cl.exe': None,
}

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

def main(name, args, paths=None):
	global libroutes
	import os

	if paths is None:
		paths = libprobe.environ_paths()

	user = libroutes.File.home()
	S = libxml.Serialization()

	for x in roles:
		contextfile = user / '.fault' / 'context' / (x + '.xml')
		contextfile.init('file')

		xml = b''.join(libxml.Data.serialize(S, None))
		with contextfile.open('wb') as f:
			f.write(xml)

if __name__ == '__main__':
	import sys
	main(sys.argv[0], sys.argv[1:])
