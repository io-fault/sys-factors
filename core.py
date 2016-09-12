"""
Core classes and data; dependents should access the
functionality from the &.library module.
"""
import sys

def outerlocals(depth = 0):
	"""
	Get the locals dictionary of the calling context.

	If the depth isn't specified, the locals of the caller's caller.
	"""
	global sys
	if depth < 0:
		raise TypeError("depth must be greater than or equal to zero")

	f = sys._getframe().f_back.f_back
	while depth:
		depth -= 1
		f = f.f_back

	return f.f_locals

# Mapping of languages to file extensions.
file_extensions = {
	'system.object.archive': ('a',),
	'system.library': ('dll', 'so', 'lib'),
	'python.extension': ('pyd',),

	'python.egg': ('egg',),
	'python.wheel': ('whl',),
	'java.jar': ('jar',),

	'resources.zip': ('zip',),
	'resources.tar': ('tar',),
	'resources.rar': ('rar',),

	'encoding-binhex': ('hqx',),
	'encoding-base64': ('base64','b64'),
	'encoding-hex': ('hex',),

	'executable': ('exe',),

	'postscript': ('ps',),
	'adobe-portable-document': ('pdf',),

	'awk': ('awk',),
	'sed': ('sed',),

	'css': ('css',),
	'xml': ('xml',),
	'html': ('htm', 'html'),
	'javascript': ('js',),

	'c-shell': ('csh',),
	'korn-shell': ('ksh',),
	'bourne-shell': ('sh',),

	'perl': ('pl',),
	'ruby': ('ruby',),
	'php': ('php',),
	'lisp': ('lisp',),
	'lua': ('lua',),
	'io': ('io',),
	'java': ('java',),

	'python': ('py',),
	'python-bytecode': ('pyo', 'pyc',),
	'pyrex': ('pyx',),

	'd': ('d',),
	'rust': ('rs',),

	'c': ('c',),
	'c++': ('c++', 'cxx', 'cpp'),
	'objective-c': ('m',),
	'bitcode': ('bc',), # llvm

	'ocaml': ('ml',),
	'ada': ('ads', 'ada'),
	'assembly': ('asm',),
	'haskell': ('hs',),

	'header': ('h',), # Purposefully ambiguous. (Can be C/C++/Obj-C)
	'c++-header': ('H', 'hpp', 'hxx'),
}

import imp
if hasattr(imp, 'cache_from_source'):
	def cache_path(path, imp=imp):
		"Given a module path, retrieve the basename of the bytecode file."
		return imp.cache_from_source(path)[:-len('.pyc')]
else:
	def cache_path(path):
		return path[:path.rfind('.py')]
del imp
