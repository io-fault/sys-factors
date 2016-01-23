"""
Extension module loader for libconstruct and bootstrap constructed extension modules.
This is not imported for loading installed packages as the modules are relocated to
allow Python's default import machinery to perform the task.
"""
import platform # 1MB memory on 64-bit systems.
import imp
import os.path
import sys
import contextlib
from . import core

platform = platform.system().lower() + '.' + platform.machine().lower()
del sys.modules['platform']

role = 'bootstrap'
extension = '.pyd'
file = 'module'
source_directory = 'src'
construction = None
enabled = True

def extension_sources(module):
	fp = getattr(module, '__origin__', module.__file__)
	return os.path.join(os.path.dirname(os.path.abspath(fp)), source_directory)

def extension_cache(module, role,
	abiflags = sys.__dict__.get('abiflags', ''),
	python_version = ''.join(map(str, sys.version_info[:2])),
	pjoin = os.path.join):
	"Calculate the directory path of the extension module using the role and module."

	dir = os.path.dirname(os.path.abspath(module.__file__))
	cache_name = '{role}:python-{version}{abiflags}.{platform}'.format(
		role = role, abiflags = abiflags,
		version = python_version, platform = platform,
	)
	return pjoin(dir, '__pycache__', cache_name)

def resolve_extension_path(module, role, pjoin=os.path.join):
	"Calculate the path of the extension module using the role and module."
	return pjoin(extension_cache(module, role), file + extension)

def conditions(target, sources, exists=os.path.exists, getmtime=os.path.getmtime) -> bool:
	"Determine whether the extension needs to be rebuilt."
	return (not exists(target) or getmtime(target) < getmtime(sources))

def load(module=None, role_override=None, internal_load_dynamic=imp.load_dynamic):
	"Load the libconstruct or bootstrap built extension module."

	global construction
	global role
	global enabled

	if module is None:
		# package modules defining a target don't have to define themselves.
		ctx = core.outerlocals()
		module = sys.modules[ctx['__name__']]

	sources = extension_sources(module)
	path = resolve_extension_path(module, role_override or role)

	if not enabled:
		module.sources = sources
		return

	rebuild = conditions(path, sources)
	if rebuild:
		if construction is None:
			role = 'bootstrap'
			path = resolve_extension_path(module, 'bootstrap')
			from . import bootstrap
			construction = bootstrap

		exc = construction.construct(path, sources, module, role)
		if exc is not None:
			raise ImportError(fullname) from exc

	try:
		mod = internal_load_dynamic(module.__name__, path)

		# rewrite the package module contents with that of the extension module
		for k, v in mod.__dict__.items():
			if k.startswith('__'):
				continue
			module.__dict__[k] = v
		module.__dict__['__shared_object__'] = mod
		mod.__path__ = module.__path__ = None
		mod.__type__ = 'extension'
		module__origin__ = mod.__origin__ = module.__file__

	except Exception:
		raise ImportError(module.__name__)

	return mod