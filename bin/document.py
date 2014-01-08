import sys
from .. import libsphinx

def main(args):
	dirs = [libsphinx.build(x, statusfile = sys.stderr, warningfile = sys.stderr) for x in args]
	for x in dirs:
		print(x)

if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))
