"""
System feature probes for executables and the runtime environment.

&.libprobe provides a set of system queries for detecting executables,
compiler collections, headers, and libraries.

[ Matrix Commands ]

/compile.c
	Compile C source into object files.
/compile.c++
	Compile C++ source into object files.
/compile.objective-c
	Compile Objective-C source into object files for linking.
/compile.haskell
	Compile Haskel source into object files for linking.
	Usually with the compiler supporting foreign interfaces providing the desired adaptions.
/compile.pyrex
	Compile Cython/Pyrex modules into C or C++ source.

/link.executable
	Link an executable.
/link.library
	Link a library for use by the system. Usually a shared library or equivalent concept.
	If the system does not support the concept of a shared library, this command will do nothing.
/link.static
	Link a static library for use by the system.
/link.dynamic
	Link a library that can be dynamically loaded by system processes.

/isolate.source.maps
	Given an static library or shared library, isolate the debugging symbols
	from the target. Usually ran unconditionally regardless of the target's role.

/coverage
	Extract coverage information for the given library and source file.
/profile
	Extract profile information for the given library and source file.
"""
import os
import subprocess
import typing
import functools
import itertools
import collections.abc
import typing

from ..routes import library as libroutes
from ..system import libexecute

def executables(
		search_paths, xset:typing.Set[str]
	) -> typing.Tuple[typing.Mapping[str, libroutes.File], typing.Set[str]]:
	"""
	Query the environment's paths for the given set of executables.

	This returns all possibilities. All paths will be scanned for each requested
	name in &xset.
	"""

	ws = set(xset)
	removed = set()
	rob = {}

	for r in search_paths:
		if not ws:
			break

		for x in ws:
			xr = r/x
			if xr.exists():
				rob[x] = xr
				removed.add(x)

		if removed:
			ws.difference_update(removed)
			removed = set()

	return rob, ws

def libraries(
		matrix:libexecute.Matrix,
		libraries:typing.Sequence[str],
		symbols:typing.Sequence[str],
	):
	"""
	Validate that the given libraries can be linked against an executable target.

	[ Parameters ]
	/matrix
		The matrix to probe.
	/libraries
		A sequence of strings identifying the shared libraries to link.
	/symbols
		A sequence of symbols to refer to in the program.
	"""
	pass

def runtime(
		matrix:libexecute.Matrix,
		compiler:collections.abc.Hashable,
		source:str,
		libraries:typing.Sequence[str],
		directories:typing.Sequence[str]=(),
		preprocessor:typing.Sequence[str]=(),
		linker='link.system.executable',
		compile_only:bool=False,
	):
	"""
	Given a &str of source code acceptable by the &compiler identified in the &matrix,
	compile, link, and execute a program returning the binary data written to standard
	output by the process.

	The process must return zero in order to identify success. If a non-zero result is
	returned the binary data written to standard error will be collected and an exception
	will be raised containing the result code and the standard error data.
	"""

	output = None
	ccmd = matrix.commands[compiler]
	lcmd = matrix.commands[linker]

	with libroutes.File.temporary() as tr:
		src = tr/'source'
		obj = tr/'object'
		exe = tr/'fault_probe_runtime_check.exe'

		src.init('file')

		with src.open('wb') as f:
			f.write(source.encode('utf-8'))

		params = ccmd.allocate()
		params['input'].append(src)
		params['output'] = obj

		lparams = lcmd.allocate()
		sl = lparams['system.libraries']
		sl.append('c')
		sl.extend(libraries)
		lparams['input'].append(obj)
		lparams['output'] = exe

		compile_ref = libexecute.Reference(matrix, ccmd)
		for k, p in params.items():
			compile_ref.update(k, p)

		if compile_only:
			link_ref = None
		else:
			link_ref = libexecute.Reference(matrix, lcmd)
			for k, p in lparams.items():
				link_ref.update(k, p)

		for ref in (compile_ref, link_ref):
			if ref is None:
				break
			env, er, args = ref.render()
			p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			so = p.stdout.read()
			se = p.stderr.read()
			r = p.wait()
		else:
			p = subprocess.Popen(
				[str(exe)],
				stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE
			)
			output = p.stdout.read()
			errors = p.stderr.read()
			rc = p.wait()

		return output

def sysctl(route, names):
	"""
	Retrieve the system control variables using (system:executable)`sysctl`.

	[Parameters]
	/route
		The route to the `sysctl` executable.
	/names
		The settings to get.
	"""
	pass
	# <x:limit/>

class Sequencing(libexecute.Sequencing):
	"""
	Command Sequencing methods for &.libconstruct.
	"""
	pass

def includes(
		matrix:libexecute.Matrix,
		compiler:collections.abc.Hashable,
		includes:typing.Sequence[str],
		directories:typing.Sequence[str]=(),
		requisites:typing.Sequence[str]=(),
	) -> bool:
	"""
	Search for &includes present in the environment described by &matrix.

	Returns a bool on whether the environment has the requested headers in its
	configuration for the designated compiler.

	The check is compiler sensitive; the configuration of a compiler can have
	arbitrary include paths, so a particular compiler must be stated in order to
	perform the check.

	[ Parameters ]
	/matrix
		The execution matrix with the desired environment and compiler command.
	/compiler
		The identifier of the &libexecute.Command instance in the &matrix.
	/includes
		A sequence of includes to test for. A sequence is used so that
		dependencies may be included prior to the actual header or headers of interest.
		The check is only interested in whether or not compilation succeeded.
	/directories
		Include search paths.
	"""

	main = "\nint main(int argc, char *argv[]) { return 0; }"
	reqs = ''.join([
		('#include <%s>\n' * len(requisites)) %requisites
	])
	includes = ''.join([
		('#include <%s>\n' * len(includes)) %includes
	])

	runtime(matrix, compiler, reqs+includes+main, (), compile_only=True)
	return True

if __name__ == '__main__':
	import sys, os
	p = os.environ['PATH']
	paths = list(map(libroutes.File.from_absolute, p.split(':')))
	present, absent = executables(paths, c_compilers)
	c = present.pop('clang')
	testing(c)
	# Perform initial development probes and emit command Matrix as XML.
