"""
Executable module taking a single parameter that emits the compilation
transcript to standard out.
"""
import sys
import pkgutil
from .. import bootstrap

if __name__ == '__main__':
	modpath = sys.argv[1]
	mloader = pkgutil.get_loader(modpath)
	bootstrap.role = sys.argv[2]
	for x in mloader.stages:
		with open(mloader.logfile(x), 'rb') as logfile:
			sys.stdout.buffer.write(logfile.read())
	sys.stdout.write("\n")
