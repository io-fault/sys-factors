"""
# Perform nothing and note that the factor type was not supported by the context.
"""
import sys
from fault.system import process

def main(inv:process.Invocation) -> process.Exit:
	sys.stderr.write("unsupported factor type\n")
	return inv.exit(101)

if __name__ == '__main__':
	process.control(main, process.Invocation.system())
