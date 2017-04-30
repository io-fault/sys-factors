"""
# Tool interfaces for extracting information from corefiles.
"""
import sys
import subprocess
import shutil

def debug(corefile, executable=sys.executable):
	"""
	# Load the debugger for a given core file, `corefile` and `executable`.
	# This will operate interactively and return the status code on exit.

	# By default, the executable is the Python executable.
	"""

	debugger = shutil.which('lldb') or shutil.which('gdb')
	return subprocess.Popen((debugger, '--core=' + corefile, executable))

gdb_snapshot = [
	'info shared',
	'thread backtrace all',
]

lldb_snapshot = [
	'image list',
	'thread apply all bt full',
]

def snapshot(corefile, executable=sys.executable):
	"""
	# Get a text dump of the corefile from either lldb or gdb.
	"""

	debugger = shutil.which('lldb')
	if debugger:
		commands = lldb_snapshot
	else:
		debugger = shutil.which('gdb')
		commands = gdb_snapshot

	p = subprocess.Popen(
		(debugger, '--core=' + corefile, executable),
		stdin=subprocess.PIPE,
		stderr=subprocess.STDOUT,
		stdout=subprocess.PIPE,
	)
	stdout, stderr = p.communicate(('\n'.join(commands)+'\n').encode('ascii'))

	return stdout
