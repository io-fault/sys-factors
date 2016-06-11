"""
Test harness access for collecting metrics.

Invoking measure requires two or more command parameters. The first is the reporting
directory, for collected data, and the remainder being packages to test.
"""
import sys
import functools

from .. import library as libdev
from .. import libmetrics

from ...system import libcore

def main(target_dir, packages):
	target_fsdict = libmetrics.libfs.Dictionary.create(
		libmetrics.libfs.Hash('fnv1a_32', depth=1), target_dir
	)

	target_fsdict[b'metrics:packages'] = b'\n'.join(x.encode('utf-8') for x in packages)

	for package in packages:
		p = libmetrics.Harness(target_fsdict, package, sys.stderr)
		p.execute(p.root(libdev.Factor.from_fullname(package)), ())
		# Build measurements.
		libmetrics.prepare(target_fsdict)

	raise SystemExit(0)

if __name__ == '__main__':
	target_dir, *packages = sys.argv[1:]
	with libcore.constraint(None):
		libmetrics.libsys.control(functools.partial(main, target_dir, packages))
