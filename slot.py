"""
Manage an identifier used for storing developer metrics regarding a project.

When tests are performed, there is a need to store the metrics describing the
events that transpired; profiling data and test fates. Rather than silently
overwriting old data, a new slot identifier can be rendered for every run.
"""
import os
import functools

from ..chronometry import lib as timelib
from ..routes import lib as routeslib

slot_environment = 'FAULT_DEV_SLOT'

# Stored inside __pycache__
python_cache = '__pycache__'
developer_cache = '__dev__'

timestamp = None
identifier = 'uninitialized'

def initialize():
	"""
	Initialize the module's timestamp and identifier globals for developer cache.
	"""
	global timestamp, identifier

	timestamp = timelib.now().truncate('second')
	if 'FAULT_DEV_SLOT' in os.environ:
		identifier = os.environ[slot_environment]
	else:
		identifier = timestamp.select("iso")

initialize()

@functools.lru_cache(32)
def prefix(route):
	return route.container / python_cache / developer_cache

def resolve(route, slot_id = None):
	"""
	Resolve the developer cache directory. If not @slot_id is provided,
	the `slot_id` in the module's globals is used to allow for modifying the current
	working slot.
	"""
	return prefix(route) / (slot_id or identifier) / route.identity

def route(filepath, from_abs = routeslib.File.from_absolute):
	"""
	route(filepath)

	Return the Route to the file's meta entry of `meta_records_name` or the route
	to the meta directory for the given file.
	"""
	f = from_abs(filepath)
	return resolve(f)
