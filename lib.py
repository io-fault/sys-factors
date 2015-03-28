import contextlib
from .abstract import ToolError

#: Default Role used by the loader.
#: The loader will use ``'debug' if __debug__`` when nothing is specified here.
role = None

#: Target DLL Roles for compilation.
known_roles = set([
	'test',
	'debug',
	'profile',
	'coverage',
	'factor',
])

role_options = []
