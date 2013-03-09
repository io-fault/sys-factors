"""

🚧 About
--------

dev is a collection of Python developer tools presented as a
modest alternative to the standard library's offering.

.. warning:: dev is a work in progress

Testing
-------

:py:mod`dev.libtest` is a protocol driven testing library. Users need not import libtest
in order to define their tests, only to run them. This means that test modules can be
imported without `dev` being available.

:py:mod:`dev.libtest` attempts to make constructing test runners as simple as possible by
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

The executable module `dev.bin.init` initializes a new package directory
complete with `setup.py` script. The following is the consistency of the
layout from a `python -m dev.bin.init package` run::

	package/
		__init__.py
		lib.py [empty "primary" module]
		test/
			test_lib.py
		bin/
		release/
			xdistutils.py [module distutils data]
			pypi.py [pypi specific data goes here]
		documentation/
			usage.rst
			project.rst
			reference.rst
			index.rst
			conf.py

"""
__pkg_bottom__ = True
