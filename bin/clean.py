"""
# Remove the work directory from the factor's cache.
# Usually used have running &.bin.incorporate.
"""
import os
import sys
import types

from fault.routes import library as libroutes
from fault.io import library as libio

import_from_fullname = libroutes.Import.from_fullname
import_from_module = libroutes.Import.from_module

def main():
	"""
	# Prepare the entire package building factor targets and writing bytecode.
	"""
	call = libio.context()
	sector = call.sector
	proc = sector.context.process

	args = proc.invocation.parameters['system']['arguments']
	env = proc.invocation.parameters['system'].get('environment')
	if not env:
		env = os.environ

	# collect packages to prepare from positional parameters
	roots = [import_from_fullname(x) for x in args]

	# Collect Python packages in the roots to build bytecode.
	next_set = list(roots)
	while next_set:
		current_set = next_set
		next_set = []

		for pkg in current_set:
			adds = pkg.subnodes()[0]
			next_set.extend(adds)
			fpi_dir = pkg.file().container / '__pycache__' / '.fpi'

			if fpi_dir.exists():
				print('removing:', str(fpi_dir))
				fpi_dir.void()

if __name__ == '__main__':
	sys.dont_write_bytecode = True
	from fault.io import command
	command.execute()
