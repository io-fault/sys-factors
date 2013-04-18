import sys
from .. import libmeta

def main(args):
	cmd, *cargs = args
	if cmd == 'void':
		libmeta.void_path(cargs[0])
	elif cmd == 'path':
		path, *metatype = cargs
		if metatype:
			print(libmeta.route(path, metatype[0]).fullpath)
		else:
			print(libmeta.route(path, 'none').container.fullpath)
	else:
		raise RuntimeError("unknown command: " + cmd)

if __name__ == '__main__':
	main(sys.argv[1:])
