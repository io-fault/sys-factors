"""
Executable module taking a single parameter that emits the compilation
transcript to standard out.
"""
import sys
import pkgutil
from .. import libloader

if __name__ == '__main__':
	modpath = sys.argv[1]
	loader = pkgutil.get_loader(modpath)
	libloader.role = sys.argv[2]
	for x in loader.stages:
		with open(loader.logfile(x), 'rb') as logfile:
			sys.stdout.buffer.write(logfile.read())
	sys.stdout.write("\n")
