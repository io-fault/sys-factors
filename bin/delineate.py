from ...factors import python
from ...routes import library as libroutes

if __name__ == '__main__':
	import sys
	r = libroutes.Import.from_fullname(sys.argv[1])
	w = sys.stdout.buffer.write
	w(b'<?xml version="1.0" encoding="utf-8"?>')
	module = r.module()
	module.__factor_composite__ = False
	i = python.document(python.Query(r), r, module)
	for x in i:
		w(x)
	w(b'\n')
	sys.stdout.flush()
