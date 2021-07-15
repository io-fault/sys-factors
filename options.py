"""
# Options parser implementation for compilation options common to compiler collections and link editors.
# Used by command line tools to construct Context reference parameters local to the command.
"""
from fault.project import types
from fault.system import files
from . import core

sourcetree = types.Reference.from_ri('type', 'http://if.fault.io/factors/lambda.sources')
systemexec = types.Reference.from_ri('type', 'http://if.fault.io/factors/system.executable')
systemlibrary = types.Reference.from_ri('reference', 'http://if.fault.io/factors/system.library')
systemdirectory = types.Reference.from_ri('reference', 'http://if.fault.io/factors/system.directory')
sourceparameter = types.Reference.from_ri('set', 'http://if.fault.io/factors/lambda.control')

def split_define_parameter(s):
	idx = s.find('=')
	if idx == -1:
		return [(s, '')]

	return [(s[:idx], s[idx+1:])]

handlers = {
	'-X': (systemexec, files.Path.from_path),
	'-I': (sourcetree, files.Path.from_path),
	'-l': (systemlibrary, files.root.__matmul__),
	'-L': (systemdirectory, files.Path.from_path),
	'-D': (sourceparameter, split_define_parameter),
	'-U': (sourceparameter, (lambda x: [(str(x), None)])),
}

def parse(arguments):
	"""
	# Parse the given arguments into a dictionary suitable for serialization into
	# a &.cc.Context parameters directory and use by &.cc.Parameters.
	"""
	for x in arguments:
		typ, shape = handlers[x[:2]]
		yield core.SystemFactor(str(typ), shape(x[2:]))
