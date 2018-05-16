"""
# Destroy the (system/filename)`__pycache__` (system/filename)`__f_cache__` directories in the
# directories given as parameters to the command.
"""

import sys
from fault.routes import library as libroutes

def descend(route, directories={'__pycache__', '__f_cache__'}):
	for x in directories:
		p = (route / x)
		if p.exists():
			path = str(p)
			assert path.endswith('/__pycache__') or path.endswith('__f_cache__')
			print('removing:', str(p))
			p.void()

	dirs = route.subnodes()[0]
	for r in dirs:
		descend(r)

def main(args, directory='__pycache__', File=libroutes.File):
	for path in args:
		fr = File.from_path(path)
		descend(fr)

if __name__ == '__main__':
	main(sys.argv[1:])
