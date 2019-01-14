"""
# Destroy the (system/filename)`__f-cache__` directories in the trees given as
# parameters to the command.
"""

import sys
import collections
from fault.system import files

default_removals = ('__f-int__', '__f-cache__', '__f_cache__')

def clear_set(names, route):
	for x in names:
		p = (route / x)
		if p.exists():
			path = str(p)
			sys.stderr.write('- %s/\n' %(str(p),))
			#p.void()

def clear_tree(names, routes):
	q = collections.deque(routes)

	while q:
		current = q.popleft()
		clear_set(names, current)
		q.extend(current.subnodes()[0])

def main(args):
	clear_tree(default_removals, [files.Path.from_path(x) for x in args])

if __name__ == '__main__':
	main(sys.argv[1:])