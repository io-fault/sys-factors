"""
Tools for enabling core dumps and resolving the location of the core files.
"""
import sys
import os
import os.path
import contextlib
import resource

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
		yield None
	finally:
		setrlimit(type, current)

if 'freebsd' in sys.platform or 'darwin' in sys.platform:
	import subprocess

	def _core_pattern():
		p = subprocess.Popen(('sysctl', 'kern.corefile'), stdout = subprocess.PIPE)
		corepat = p.stdout.read().decode('utf-8')
		prefix, corefile = corepat.split(':', 1)
		return corefile.strip()

elif 'linux' in sys.platform:
	def _core_pattern():
		with open('/proc/sys/kernel/core_pattern') as f:
			return f.read()
else:
	def _core_pattern():
		raise RuntimeError("cannot resolve coredump pattern for this platform")

def core_pattern():
	"""
	Return the configure core file dump pattern that designates where a core file will be
	saved.
	"""
	return _core_pattern()

def resolve(pid, binary = sys.executable):
	"""
	Using the given information, resolve the location of the core file.
	"""
	pat = core_pattern()
	if pat.startswith('|'):
		# linux allows piping cores to specific commands.
		# Can't handle it without changing the core_pattern.
		return None

	execname = os.path.basename(binary)

if __name__ == '__main__':
	# make the core pattern usable
	pass
