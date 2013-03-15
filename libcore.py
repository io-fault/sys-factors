"""
Tools for enabling core dumps and resolving the location of the core files.
"""
import sys
import os
import os.path
import contextlib
import resource

if 'freebsd' in sys.platform or 'darwin' in sys.platform:
	def kernel_core_pattern():
		import subprocess
		p = subprocess.Popen(('sysctl', 'kern.corefile'),
			stdout = subprocess.PIPE, stderr = None, stdin = None)
		corepat = p.stdout.read().decode('utf-8')
		prefix, corefile = corepat.split(':', 1)
		return corefile.strip()
elif os.path.exists('/proc/sys/kernel/core_pattern'):
	def kernel_core_pattern():
		with open('/proc/sys/kernel/core_pattern') as f:
			return f.read()
else:
	def kernel_core_pattern():
		raise RuntimeError("cannot resolve coredump pattern for this platform")

@contextlib.contextmanager
def dumping(
	setting = -1,
	getrlimit = resource.getrlimit,
	setrlimit = resource.setrlimit,
	type = resource.RLIMIT_CORE
):
	"""
	dumping()

	Enable or disable core dumps during the context. Useful for managing tests that may dump core.

	Typical use::

		with dev.libcore.dumping():
			...

	Core dumps can disabled by designating size::

		with dev.libcore.dumping(0):
			...
	"""
	setting = setting or 0
	try:
		current = getrlimit(type)
		setrlimit(type, (setting, setting))
		if setting:
			yield os.environ.get('COREPATTERN', '/cores/core.{pid}').format
		else:
			yield None
	finally:
		setrlimit(type, current)

if __name__ == '__main__':
	pass
