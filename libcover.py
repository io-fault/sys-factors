"""
Tools for collecting coverage information.
Coverage data collection and management.
"""
import io
import os.path
import contextlib

@contextlib.contextmanager
def python():
	"""
	Enable Python coverage.
	"""
	from coverage import coverage
	xml = io.StringIO()
	cov = coverage()
	try:
		cov.start()
		yield None
	finally:
		cov.stop()
		cov.xml_report(xml)
		cov.erase()

@contextlib.contextmanager
def c():
	"""
	Enable C-API coverage.
	"""
	cmodules = []
	import c.lib
	import c.loader

	with \
	c.lib.features('coverage'), \
	c.loader.CLoader.tracing(lambda x: cmodules.append(x)):
		try:
			yield None
		finally:
			# get directories that
			dirs = [os.path.basename(x.cprefix) for x in cmodules]

@contextlib.contextmanager
def all():
	"""
	Context Manager enabling coverage for all forms of code recognized by the dev package.
	"""
	with c(), python():
		yield None
