"""
Prepare the targets of a package hierachry for direct use. This executes &.bin.construct
and &.bin.induct for the same context and role.

Usual entry point for managing a package's build during development.
"""
import os
import sys
import subprocess
import contextlib

from ...chronometry import library as libtime

def status(text, newline=True, target=sys.stderr, color=(lambda x: '\x1b[38;5;202m' + x + '\x1b[0m')):
	target.write(color(text))
	if newline:
		target.write('\n')
	target.flush()

@contextlib.contextmanager
def timing(text, target=sys.stderr, color=(lambda x: '\x1b[38;5;34m' + x + '\x1b[0m')):
	try:
		i = libtime.clock.meter()
		sys.stderr.write(color('[' + libtime.now().select('iso') + '] '))
		status(text)
		next(i)
		yield i
	finally:
		duration = next(i)
		status('duration ' + str(duration.select('second')) + 's')
		sys.stderr.write('\n')

def exit(rc):
	status('exit: ' + str(rc) + '; ', newline=False)
	return rc

def exe(name, *args, pkg = __package__):
	cmd = (sys.executable, '-m', pkg + '.' + name) + args
	status(' '.join(cmd))
	return subprocess.Popen(cmd)

def main(instance, pkg):
	with timing('constructing'):
		crc = exit(exe('construct', pkg).wait())

	if crc != 0:
		status("Exiting early due to construction failure.")
		status("Logs are in __pycache__.")
		raise SystemExit(100)

	with timing('inducting'):
		irc = exit(exe('induct', pkg).wait())

if __name__ == '__main__':
	os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
	try:
		del os.environ['PYTHONOPTIMIZE']
	except KeyError:
		pass
	sys.dont_write_bytecode = True
	main(*sys.argv)
