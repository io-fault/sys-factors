"""

🐜 About
--------

dev is a collection of Python developer tools presented as a
modest alternative to the standard library's offering.

.. warning:: dev is a work in progress.

Testing
-------

:py:mod`.libtest` is a protocol driven testing library. Users need not import libtest
in order to define their tests, only to run them. This means that test modules can be
imported without `dev` being available.

:py:mod:`.libtest` attempts to make constructing test runners as simple as possible by
keeping the interface as simple as possible.

The test object provides an abstraction that allows for checks to be performed using
standard comparison operators::

	import something

	def test_something(test):
		expectation = (2,5)
		test/expectation == something.calculate(1)
		test/expectation > something.render()

	if __name__ == '__main__':
		import dev.libtest; dev.libtest.execmodule()

Skeletons
---------

The executable module :py:mod:`.bin.init` initializes a new package directory
complete with `setup.py` script. The following is the consistency of the
layout from a `python -m fault.dev.bin.init package` run::

	package/
		__init__.py
		abstract.py [area for abstract classes and data used across implementations]
		lib.py [empty primary access module; import entry points here into here]
		test/
			__init__.py
			__main__.py
			test_lib.py
		bin/
			__init__.py
			rattle.py
		documentation/
			usage.rst
			project.rst
			reference.rst
			index.rst
			glossary.rst

Documentation
-------------

:py:mod:`.libsphinx` provides a high-level build function for running a sphinx-build
command for a project. Given a dev.skeleton conforming project, a sphinx configuration
file is only useful for customization, which is rarely necessary for small projects.
"""
__pkg_bottom__ = True
