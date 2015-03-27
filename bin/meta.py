import sys
from .. import libmeta

def main(args):
	cmd, *cargs = args
	if cmd == 'void':
		path = cargs[0]
		fr = routeslib.File.from_path(path)

		(fr / libmeta.python_cache).void()
		for x in fr.subnodes()[0]:
			p = (x / libmeta.python_cache)
			assert '/__pycache__/' in p.fullpath
			p.void()
	elif cmd == 'path':
		path, *metatype = cargs
		if metatype:
			print(libmeta.route(path, metatype[0]).fullpath)
		else:
			print(libmeta.route(path, 'none').container.fullpath)
	elif cmd == 'coverage':
		for x in cargs:
			libmeta.creport(x)
	else:
		raise RuntimeError("unknown command: " + cmd)

if __name__ == '__main__':
	main(sys.argv[1:])
