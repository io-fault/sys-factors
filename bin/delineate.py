"""
# Emit an empty (fragments)`instance`.

# In cases where language introspection is not supported, a fallback must be
# available for making product snapshots possible. &.bin.configure uses
# this as the default when a given language is not supported.
"""
import sys

from fault.system import process
from fault.system import files
from fault.xml import library as libxml
from .. import fragments

prefix = b'<factor xmlns="http://fault.io/xml/fragments"><void>'
suffix = b'</void></factor>\n'

def main(inv):
	try:
		filepath, = inv.args
		route = files.Path.from_path(filepath)
	except ValueError:
		route = files.Path.from_absolute('/dev/stdin')

	out = sys.stdout.buffer
	out.write(prefix)
	lines = fragments.source_element(libxml.Serialization(), route)
	out.writelines(lines)
	out.write(suffix)

	return inv.exit(0)

if __name__ == '__main__':
	process.control(main, process.Invocation.system())
