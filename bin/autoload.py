import os.path
import site
from ..loader import __name__ as loader_module_path

pthfile = """# THIS FILE MAKES THE *.py.(c|m|c++) FILES IMPORTABLE
import {path}; {path}.install()
"""

def render(contents = pthfile, filename = 'xeno.pth'):
	return contents.format(path = loader_module_path)

def autoload():
	"""
	Write the output of :py:func:`.render` to a dot-pth file in site packages directory.
	"""
	dir = site.getsitepackages()[0]
	with open(os.path.join(dir, filename), 'w') as f:
		f.write(render())

if __name__ == '__main__':
	autoload()
