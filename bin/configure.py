"""
# Command interface to a Materialized Construction Context.
"""
import sys
import os
from fault.system import library as libsys
from fault.routes import library as libroutes
from .. import fs

def main(inv:libsys.Invocation) -> libsys.Exit:
	typ, path, *args = inv.args
	typ = typ.capitalize()
	Imp = getattr(fs, typ) # get class for specified directory protocol
	i = Imp(libroutes.File.from_path(path))

	ctx = os.environ['CONTEXT']
	dev = os.path.join(ctx, 'execute')

	if args:
		subject = args[0]
	else:
		subject = 'check'

	if subject == 'check':
		os.chdir(os.path.join(ctx, 'scanner'))
		os.spawnv(os.P_WAIT, dev, [dev, 'construct', 'probes'])
		os.spawnv(os.P_WAIT, dev, [dev, 'induct', 'probes'])
	elif subject == 'instrumentation':
		target = os.path.join(ctx, 'lib', 'python', 'instrumentation')
		if not os.path.exists(target):
			os.spawnv(os.P_WAIT, dev, [dev, 'template', str(target), 'context', 'instrumentation'])

		tools = args[1:]
		if tools:
			pass

	return inv.exit(0)

if __name__ == '__main__':
	libsys.control(main, libsys.Invocation.system())
