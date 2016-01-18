"""
Manage an identifier used for storing developer metrics regarding a project.

When tests are performed, there is a need to store the metrics describing the
events that transpired; profiling data and test fates. Rather than silently
overwriting old data, a new slot identifier can be rendered for every run.
"""
import os
import functools

from ..routes import library as routeslib

slot_environment = 'FAULT_DEV_SLOT'

# Stored inside __pycache__
python_cache = '__pycache__'
developer_cache = '__dev__'

timestamp = None
identifier = 'uninitialized'

def initialize(slot_environment = slot_environment):
	"""
	Initialize the module's timestamp and identifier globals for developer cache.

	If the slot environment variable, FAULT_DEV_SLOT, is not set, an identifier
	will generated based on the current demotic time identified by chronometry.
	When an identifier is generated, it is set to the environment so that child
	processes automatically use it regardless of how they're executed.

	If a new slot should be used by a child, the environment variable should be unset
	or set to an empty string. Using fault.system's Invocation interface, the environment should
	be altered using its environment variable parameters.

	This function is automatically called when the module is imported.
	"""
	global timestamp, identifier
	from ..chronometry import library as timelib

	timestamp = timelib.now().truncate('second')
	if os.environ.get(slot_environment, None):
		# Only use the identifier if its not an empty string.
		identifier = os.environ[slot_environment]
	else:
		identifier = timestamp.select("iso")
		os.environ[slot_environment] = identifier

initialize()

@functools.lru_cache(32)
def prefix(route):
	return route.container / python_cache / developer_cache

def resolve(route, slot_id = None):
	"""
	Resolve the developer cache directory. If no &slot_id is provided,
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
