"""
System feature probes for executables and the runtime environment.

&.libprobe provides a set of system queries for detecting executables,
compiler collections, headers, and libraries.
"""
import os
import subprocess
import typing
import functools
import itertools
import collections.abc
import typing
import types

from . import libconstruct
from . import libfactor
from ..routes import library as libroutes
from ..io import library as libio

def fs_routes(i:typing.Iterator[str]) -> typing.Sequence[libroutes.File]:
	"""
	Construct a &list of &libroutes.File instances from the given
	iterator of strings.
	"""
	global libroutes
	return list(map(libroutes.File.from_absolute, i))

def environ_paths(env='PATH', sep=os.pathsep):
	"""
	Construct a sequence of &libroutes.File instances to the paths stored
	in an environment variable. &os.environ is referred to upon
	each invocation, no caching is performed so each call represents
	the latest version.

	Defaults to `PATH`, &environ_paths can select an arbitrary environment variable
	to structure using the &env keyword parameter.

	This function exists to support &search as `search(environ_paths(), {...})` is
	the most common use case.

	[ Parameters ]
	/env
		The environment variable containing absolute paths.
	/sep
		The path separator to split the environment variable on.
	"""
	global os
	global fs_routes

	s = os.environ[env].split(sep)
	seq = fs_routes(s)

	return seq

def search(search_paths:typing.Sequence[str], xset:typing.Set[str]
	) -> typing.Tuple[typing.Mapping[str, libroutes.File], typing.Set[str]]:
	"""
	Query the sequence of search paths for the given set of files.

	All paths will be scanned for each requested identifier in &xset. When an identifier
	is found to exist, it is removed from the set that is being scanned for causing
	the first path match to be the one returned.
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

def executables(xset:typing.Set[str]):
	"""
	Query the (env)`PATH` for executables with the exact name.
	Returns a pair whose first item is the matches that currently exist,
	and the second is the set of executables that were not found in the path.
	"""
	global search, environ_paths
	return search(environ_paths(), xset)

def prepare(
		directory,
		context,
		language:collections.abc.Hashable,
		source:str,
		libraries:typing.Sequence[str]=(),
		directories:typing.Sequence[str]=(),
		preprocessor:typing.Sequence[str]=(),
		ftype='system.executable',
		compile_only:bool=False,
		lmap={
			'c': 'c',
			'c++': 'cxx',
			'objective-c': 'm',
		}
	) -> typing.Tuple[libroutes.File, libconstruct.Construction]:
	"""
	Prepare a probe by initializing the given &directory as a composite factor
	containing a single source file whose content is defined by &source. Often, &directory
	is a temporary directory created by &..routes.library.File.temporary.

	The reduction of the composite (executable file) with respect to the &context and the
	&libconstruct.Construction instance are returned in a &tuple. After construction is
	complete, the executable reduction should be executed in order to retrieve the data
	collected by the sensors.
	"""

	output = None

	src = directory/'src'
	exe = directory/'fault_probe_runtime_check.exe'
	cache = directory/'__pycache__'
	fsrc = src / ('probe.' + lmap[language])
	fsrc.init('file')

	mod = types.ModuleType("fault_probe")
	mod.__file__ = (str(directory / '__init__.py'))
	mod.__factor_type__ = 'system.executable'
	mod.libraries = set(libraries)
	mod.library_directories = set(directories)
	mod.source_parameters = list(preprocessor)

	with fsrc.open('wb') as f:
		f.write(source.encode('utf-8'))

	return libfactor.reduction(None, context, 'debug', module=mod), \
		libconstruct.Construction(context, 'debug', [('fault_probe', mod)])

def _execute_probe(factor):
	p = subprocess.Popen(
		[str(factor)],
		stdin=None,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
	)
	output = p.stdout.read()
	errors = p.stderr.read()
	rc = p.wait()

	return output

def runtime(language, source, **parameters):
	tr = None
	cxn = None
	exe = None

	def init(unit):
		nonlocal tr, cxn, exe
		s = libio.Sector()
		s.subresource(unit)
		unit.place(s, "bin", "construction")
		unit.context.enqueue(s.actuate)
		exe, cxn = prepare(tr, 'host', language, source, **parameters)
		s.dispatch(cxn)

	with libroutes.File.temporary() as tr:
		with libio.parallel(init) as u:
			pass

		out = _execute_probe(exe)

	return out

def sysctl(names, route=None):
	"""
	Retrieve the system control variables using (system:executable)`sysctl`.

	[Parameters]
	/route
		The route to the `sysctl` executable.
	/names
		The settings to get.
	"""
	if route is None:
		found, missing = executables({'sysctl'})
		if missing:
			raise RuntimeError("no sysctl command found")
		route = found.pop('sysctl')

	command = [route]
	command += names

def includes(
		language:collections.abc.Hashable,
		includes:typing.Sequence[str],
		requisites:typing.Sequence[str]=(),
		**parameters
	) -> bool:
	"""
	Search for &includes present in the environment described by &matrix.

	Returns a bool on whether the environment has the requested headers in its
	configuration for the designated compiler.

	The check is compiler sensitive; the configuration of a compiler can have
	arbitrary include paths, so a particular compiler must be stated in order to
	perform the check.

	[ Parameters ]
	/language
		The identifier of the language that is to be compiled.
	/includes
		A sequence of includes to test for. A sequence is used so that
		dependencies may be included prior to the actual header or headers of interest.
		The check is only interested in whether or not compilation succeeded.
	"""

	main = "\nint main(int argc, char *argv[]) { return 0; }"

	reqs = ''.join([
		('#include <%s>\n' * len(requisites)) %requisites
	])
	includes = ''.join([
		('#include <%s>\n' * len(includes)) %includes
	])

	return runtime(language, reqs+includes+main, **parameters) is not None
