"""
Perform the full procedure for constructing an inspectable snapshot of a product.

This executes sequence of executable modules to produce a snapshot for publication.

	# &.bin.construct [host:optimal]
	# &.bin.construct [inspect:metrics]
	# &.bin.construct [host:metrics]
	# &.bin.measure
	# &.factors.bin.instantiate
	# &.bin.validate [host:optimal]
"""
import os
import sys
import subprocess
import contextlib

from ...factors import bin as factors_bin
from ...routes import library as libroutes
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

def exe(name, *args, pkg = __package__):
	cmd = (sys.executable, '-m', pkg + '.' + name) + args
	status(' '.join(cmd))
	return subprocess.Popen(cmd)

def main(instance, pkg):
	os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
	try:
		del os.environ['PYTHONOPTIMIZE']
	except KeyError:
		pass

	with timing('preparing [host:optimal]'):
		os.environ['FPI_CONTEXT'] = 'host'
		os.environ['FPI_PURPOSE'] = 'optimal'
		exit(exe('prepare', pkg).wait())

	with timing('constructing [inspect:optimal]'):
		os.environ['FPI_CONTEXT'] = 'inspect'
		os.environ['FPI_PURPOSE'] = 'optimal'
		exit(exe('construct', pkg).wait())

	del os.environ['PYTHONDONTWRITEBYTECODE']

	with timing('preparing [host:metrics]'):
		os.environ['FPI_CONTEXT'] = 'host'
		os.environ['FPI_PURPOSE'] = 'metrics'
		exit(exe('construct', pkg).wait())

	with libroutes.File.temporary() as d:
		m = d / 'metrics'
		m.init('directory')
		with timing('measuring coverage and performance with project tests'):
			exit(exe('measure', str(m), pkg).wait())

		with timing('instantiating snapshot'):
			exit(exe('instantiate', instance, str(m), pkg=factors_bin.__name__).wait())

	with timing('validating'):
		raise SystemExit(exe('validate', pkg).wait())

if __name__ == '__main__':
	main(*sys.argv[1:])
