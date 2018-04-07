"""
# Destroy the (system:directory)`__pycache__` directories in the
# directories given as parameters to the command.
"""

import sys
from fault.routes import library as libroutes

def descend(route, directory='__pycache__'):
	p = (route / directory)
	if p.exists():
		assert '/__pycache__' in p.fullpath
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
