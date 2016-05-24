"""
Test surveys collecting coverage and profile information regarding the tests.

Invoking survey requires two or more command parameters. The first is the reporting
directory, surveyed information, and the remainder being packages to test.
"""
import sys
import functools

from . import prepare

from .. import library as libdev
from .. import libsurvey

from ...system import libcore

def main(target_dir, packages):
	# Set test role. Per project?
	# libconstruct.role = 'test'
	prepare.main(*packages, role='survey', mount_extensions=False)

	target_fsdict = libsurvey.libfs.Dictionary.create(
		libsurvey.libfs.Hash('fnv1a_32', depth=1), target_dir
	)

	target_fsdict[b'survey:packages'] = b'\n'.join(x.encode('utf-8') for x in packages)

	for package in packages:
		p = libsurvey.Harness(target_fsdict, package, sys.stderr)
		p.execute(p.root(libdev.Factor.from_fullname(package)), ())
		# Build measurements.
		libsurvey.prepare(target_fsdict)

	raise SystemExit(0)

if __name__ == '__main__':
	target_dir, *packages = sys.argv[1:]
	with libcore.constraint(None):
		libsurvey.libsys.control(functools.partial(main, target_dir, packages))
