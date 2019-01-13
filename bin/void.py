"""
# Construct a data profile file describing the contents of the source files.
"""
import sys
import hashlib
import collections

from fault.system import process
from fault.system import files

def measure_source(route):
	lc = 0
	d = b''
	size = 0
	h = hashlib.new('sha256', b'')
	depth = collections.Counter()

	with open(str(route), 'rb') as f:
		continued = True
		while continued:
			buf = f.read(2048)
			size += len(buf)
			h.update(buf)

			if not buf:
				continued = False
				lc += 1
			else:
				d += buf
				lines = d.split(b'\n')
				for x in lines:
					il = len(x) - len(x.lstrip(b'\t'))
					depth[il] += 1

				lc += len(lines) - 1
				d = lines[-1]

	return size, h, lc

def main(inv:process.Invocation) -> process.Exit:
	out, *inf = map(files.Path.from_path, inv.args)
	template = "[%s]\nsize: %d\nsha1_256: %s\nlines: %d\n"

	outlines = []
	for r in inf:
		size, hash, lc = measure_source(r)
		outlines.append(template % (str(r), size, hash.hexdigest(), lc))

	out.set_text_content('\n'.join(outlines))
	return inv.exit(0)

if __name__ == '__main__':
	process.control(main, process.Invocation.system())
