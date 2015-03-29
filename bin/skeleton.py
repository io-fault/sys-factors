"""
initialize a new project package using the @skeleton package directory.
"""
import os.path

def ignore(dir, names):
	return [
		x for x in names
		if x.endswith('.pyc') or x.endswith('.pyo') or x == '__pycache__'
	]

def main(project_name):
	from .. import skeleton
	import shutil
	root = os.path.dirname(skeleton.__file__)
	root = os.path.realpath(root)
	shutil.copytree(root, project_name, ignore = ignore)

if __name__ == '__main__':
	import sys
	main(sys.argv[1])
