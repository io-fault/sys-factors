import sys
from .. import libsphinx

def main(args):
	for x in args:
		libsphinx.build(x, statusfile = sys.stderr, warningfile = sys.stderr)

if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))
