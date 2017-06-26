"""
# Emit an empty (xml/fragments)`instance`.

# In cases where language introspection is not supported, a fallback must be
# available for making product snapshots possible. &.bin.configure uses
# this as the default when a given language is not supported.
"""
import sys
from ...system import library as libsys
from ...routes import library as libroutes
from ...xml import library as libxml
from .. import fragments

prefix = b'<factor xmlns="http://fault.io/xml/fragments"><void>'
suffix = b'</void></factor>\n'

def main(inv):
	filepath, = inv.args
	route = libroutes.File.from_path(filepath)

	out = sys.stdout.buffer
	out.write(prefix)
	lines = fragments.source_element(libxml.Serialization(), route)
	out.writelines(lines)
	out.write(suffix)
	sys.exit(0)

if __name__ == '__main__':
	libsys.control(main, libsys.Invocation.system())
