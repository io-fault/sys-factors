"""
Tools and libraries for supporting a development environment.
Constructing, debugging, profiling, testing and deploying software.

Construction
------------

@libconstruct provides the necessary functionality to process project targets into files
usable by the host operating system.

Testing
-------

@libtest is a dictionary protocol driven testing library. Users need not import @libtest
in order to define their tests, only to run them. This means that test modules can be
imported without @project being available.

@libtest attempts to make constructing test runners as simple as possible by
keeping the interface as simple as possible.

The test object provides an abstraction that allows for checks to be performed using
standard comparison operators::

	import something

	def test_something(test):
		expectation = (2,5)
		test/expectation == something.calculate(1)
		test/expectation > something.render()

	if __name__ == '__main__':
		import fault.development.libtest as libtest
		import sys; libtest.execute(sys.modules[__name__])

Skeletons
---------

@bin.skeleton initializes a new package directory
complete with `setup.py` script. The following is the consistency of the
layout from a `python -m fault.development.bin.skeleton package_name` run::

	package_name/
		__init__.py
		abstract.py [area for abstract classes and data used across implementations]
		library.py [empty primary access module]
		test/
			__init__.py
			__main__.py
			test_library.py
		bin/
			__init__.py
			exe.py
		documentation/
			__init__.py
			usage.rst

Documentation
-------------

API documentation is extracted into an XML format with @libdocument. The XML provides
significant details about the contents of a module and can be easily converted into a
display format.
"""
__pkg_bottom__ = True
