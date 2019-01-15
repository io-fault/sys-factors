"""
# System feature probes for executables and the runtime environment.
"""
import os
import typing
import functools
import collections.abc

from fault.system import files

def fs_routes(i:typing.Iterator[str]) -> typing.Sequence[files.Path]:
	return list(map(files.Path.from_absolute, i))

def environ_paths(env='PATH', sep=os.pathsep):
	"""
	# Construct a sequence of &files.Path instances to the paths stored
	# in an environment variable. &os.environ is referred to upon
	# each invocation, no caching is performed so each call represents
	# the latest version.

	# Defaults to `PATH`, &environ_paths can select an arbitrary environment variable
	# to structure using the &env keyword parameter.

	# This function exists to support &search as `search(environ_paths(), {...})` is
	# the most common use case.

	# [ Parameters ]
	# /env/
		# The environment variable containing absolute paths.
	# /sep/
		# The path separator to split the environment variable on.
	"""

	s = os.environ[env].split(sep)
	seq = fs_routes(s)

	return seq

def search(
		search_paths:typing.Sequence[str],
		xset:typing.Set[str]
	) -> typing.Tuple[typing.Mapping[str, files.Path], typing.Set[str]]:
	"""
	# Query the sequence of search paths for the given set of files.

	# All paths will be scanned for each requested identifier in &xset. When an identifier
	# is found to exist, it is removed from the set that is being scanned for causing
	# the first path match to be the one returned.
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
	# Query the (system/envvar)`PATH` for executables with the exact name.
	# Returns a pair whose first item is the matches that currently exist,
	# and the second is the set of executables that were not found in the path.
	"""
	return search(environ_paths(), xset)

def select(paths, possibilities, preferences):
	"""
	# Select a file from the given &paths using the &possibilities and &preferences
	# to identify the most desired.
	"""

	# Override for particular version
	possible = set(possibilities)

	found, missing = search(paths, tuple(possible))
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

def sysctl(names, route=None):
	"""
	# Retrieve the system control variables using (system:executable)`sysctl`.

	# [ Parameters ]
	# /route/
		# The route to the `sysctl` executable.
	# /names/
		# The settings to get.
	"""

	if route is None:
		found, missing = executables({'sysctl'})
		if missing:
			raise RuntimeError("no sysctl command found")
		route = found.pop('sysctl')

	command = [route]
	command += names
