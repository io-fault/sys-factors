"""
Construct the system modules and Python bytecode of a set of packages.
"""
import importlib
from .. import libconstruct

def main(role, *modules):
	"""
	Construct the set of modules using the given role.

	The target dependency tree is traversed and updated for each module and its
	requirements.
	"""
	for x in modules:
		module = importlib.import_module(x)
		libconstruct.manage(module, role)

if __name__ == '__main__':
	import sys
	main(sys.argv[1], *sys.argv[2:])
