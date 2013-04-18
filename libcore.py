"""
Tools for enabling core dumps and resolving the location of the core files.
"""
import sys
import os
import os.path
import contextlib
import functools
import subprocess
import shutil

try:
	import resource
except ImportError:
	import types
	resource = types.ModuleType("resource-null", "this platform does not have the resource module")
	del types
	def nothing(*args):
		pass
	resource.getrlimit = nothing
	resource.setrlimit = nothing
	resource.RLIMIT_CORE = 0
	del types, nothing

# Replace this with a sysctl c-extension
if os.path.exists('/proc/sys/kernel/core_pattern'):
	def kernel_core_pattern():
		with open('/proc/sys/kernel/core_pattern') as f:
			return f.read()
elif 'freebsd' in sys.platform or 'darwin' in sys.platform:
	def kernel_core_pattern():
		import subprocess
		p = subprocess.Popen(('sysctl', 'kern.corefile'),
			stdout = subprocess.PIPE, stderr = None, stdin = None)
		corepat = p.stdout.read().decode('utf-8')
		prefix, corefile = corepat.split(':', 1)
		return corefile.strip()
else:
	def kernel_core_pattern():
		raise RuntimeError("cannot resolve coredump pattern for this platform")

def corelocation(pid, pattern = functools.partial(os.environ.get, 'COREPATTERN', '/cores/core.{pid}')):
	import getpass
	return pattern().format(**{'pid': pid, 'uid': os.getuid(), 'user': getpass.getuser(), 'home': os.environ['HOME']})

@contextlib.contextmanager
def dumping(
	size_limit = -1,
	getrlimit = resource.getrlimit,
	setrlimit = resource.setrlimit,
	type = resource.RLIMIT_CORE
):
	"""
	dumping(size_limit = -1)

	Enable or disable core dumps during the context. Useful for managing tests that may dump core.

	Typical use::

		with dev.libcore.dumping():
			...

	Core dumps can disabled by designating zero size::

		with dev.libcore.dumping(0):
			...
	"""
	size_limit = size_limit or 0
	try:
		current = getrlimit(type)
		setrlimit(type, (size_limit, size_limit))
		yield None
	finally:
		setrlimit(type, current)

def debug(corefile, executable = sys.executable):
	"""
	debug(corefile, executable = sys.executable)

	Load the debugger for a given core file, `corefile` and `executable`.
	This will operate interactively and return the status code on exit.

	By default, the executable is the Python executable.
	"""
	debugger = shutil.which('lldb') or shutil.which('gdb')
	p = subprocess.Popen((debugger, '--core=' + corefile, executable))
	return p.wait()

gdb_snapshot = [
	'info shared',
	'thread backtrace all',
]

lldb_snapshot = [
	'image list',
	'thread apply all bt full',
]

def snapshot(corefile, executable = sys.executable):
	"""
	Get a text dump of the corefile.
	"""
	debugger = shutil.which('lldb')
	if debugger:
		commands = lldb_snapshot
	else:
		debugger = shutil.which('gdb')
		commands = gdb_snapshot

	p = subprocess.Popen((debugger, '--core=' + corefile, executable))
	p.wait()
