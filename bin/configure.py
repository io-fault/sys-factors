"""
# Command interface to a Materialized Construction Context.
"""
import sys
import os
from ...system import library as libsys
from ...routes import library as libroutes
from .. import fs

def main(inv:libsys.Invocation):
	typ, path, *args = inv.args
	typ = typ.capitalize()
	Imp = getattr(fs, typ) # get class for specified directory protocol
	i = Imp(libroutes.File.from_path(path))

	ctx = os.environ['CONTEXT']
	dev = os.path.join(ctx, 'develop')
	os.chdir(os.path.join(ctx, 'scanner'))
	args = sys.argv[1:]
	os.spawnv(os.P_WAIT, dev, [dev, '-g', 'construct', 'probes'])
	os.spawnv(os.P_WAIT, dev, [dev, '-g', 'induct', 'probes'])

	sys.exit(0)

if __name__ == '__main__':
	libsys.control(main, libsys.Invocation.system())
