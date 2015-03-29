"""
Executable modules with significant command line interfaces are organized into the "bin"
package.
"""

def main(args):
	print(args)

if __name__ == '__main__':
	import sys
	main(sys.argv)
