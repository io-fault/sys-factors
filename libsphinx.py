"""
libsphinx provides a small function for building sphinx project documentation based on a
dev.skeleton type project. Author and version data are supplied by the package's
:py:mod:`project` module and the documentation is resolved by the package's
:py:mod:`documentation` module. With packages that follow the dev.skeleton protocol,
no sphinx configuration is actually needed.

The :py:func:`build` function provides a foundation for automated
builds of sphinx documentation for dev.skeleton conforming projects. Overrides for custom
styling can be passed in as parameters so publication jobs can be tailored accordingly
without interference from a local sphinx configuration.
"""
import sys
import os
import importlib
import sphinx.application

def build(
	package,
	path = None,
	target = 'html',
	style = 'sphinx',
	templates = None,
	static = None,
	statusfile = None,
	warningfile = None
):
	"""
	build(package, path = None, target = 'html', style = 'sphinx')

	:param package: The Python package whose documentation is being built.
	:type package: :py:class:`str`
	:param path: The file system directory to build the target product in.
	:type path: :py:class:`str`
	:param style: The pygments style to use.
	:type style: :py:class:`str`
	:param statusfile: Where to write status messages.
	:param warningfile: Where to write warning messages.

	Build the Sphinx documentation for the specified dev-protocol conforming project.
	"""
	# pkg.project module holding author information
	context = '.'.join((package, 'project'))
	contextmod = importlib.import_module(context)

	docmodpath = '.'.join((package, 'documentation'))
	docmod = importlib.import_module(docmodpath)

	docdir = os.path.dirname(os.path.realpath(docmod.__file__))
	if path is None:
		path = os.path.join(docdir, target)
	abspath = os.path.realpath(path)

	sphinx_conf = os.path.join(docdir, 'conf.py')
	if os.path.exists(sphinx_conf):
		confdir = docdir
	else:
		confdir = None

	major, minor, *remainder = map(str, getattr(contextmod, 'version_info', (0, 0)))
	forkname = getattr(contextmod, 'fork', '')
	meaculpa = getattr(contextmod, 'meaculpa', '')

	revision = meaculpa + '/' + forkname + ' v' + major + '.' + minor

	config = dict(
		project = package,
		htmlhelp_basename = package,

		rst_prolog = "",
		rst_epilog = "",

		source_suffix = '.rst',
		version = revision,
		release = revision,
		today_fmt = '%B %d, %Y',
		pygments_style = 'sphinx',
		master_doc = 'index'
	)

	dwb = sys.dont_write_bytecode
	sys.dont_write_bytecode = True
	try:
		s = sphinx.application.Sphinx(
			docdir, confdir, abspath,
			os.path.join(abspath, '.doctrees'),
			target,
			confoverrides = config,
			freshenv = True,
			status = statusfile,
			warning = warningfile,
			tags = []
		)
		s.setup_extension('sphinx.ext.autodoc')
		s.setup_extension('sphinx.ext.viewcode')
		s.build(force_all = True)
	finally:
		sys.dont_write_bytecode = dwb

	return abspath
