"""
Executable module taking a single parameter that emits the compilation
transcript to standard out.
"""
import sys
import importlib

from ..probes import libpython

from ...system import libfactor
from ...routes import library as libroutes

if __name__ == '__main__':
	command, module_fullname, context, role, *files = sys.argv

	ir = libroutes.Import.from_fullname(module_fullname)
	target_module = importlib.import_module(str(ir)) # import "$1"
	if context == '-':
		if libpython in target_module.__dict__.values():
			from ..libconstruct import python_triplet as context
		else:
			context = 'inherit'

	logdir = libfactor.cache_directory(target_module, context, role, 'log')

	if files:
		files = [logdir.extend(x.split('/')) for x in files]
	else:
		files = logdir.tree()[1]

	for logfile in files:
		sys.stdout.write('[' + str(logfile) + ']\n')
		if not logfile.exists():
			sys.stdout.write('! ERROR: File does not exist.\n')
			continue

		with logfile.open('rb') as f:
			log = f.read()
			if log:
				sys.stdout.buffer.write(log)
				sys.stdout.write("\n")
			else:
				sys.stdout.write('! NOTE: Empty logfile.\n')
