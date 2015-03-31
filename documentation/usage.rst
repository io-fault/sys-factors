=====
Usage
=====

This chapter describes some of the high-level concepts employed by fault.development.

Project Initialization
======================

Skeleton Python packages can be initialized using the :py:mod:`.bin.init`
module. It's an executable module and should be used with the "-m" option to the
interpreter::

	python3 -m fault.development.bin.skeleton mywork

Testing
=======

Writing Tests
-------------

The :py:mod:`.libtest` module provides a means to gather and execute callable
objects that performs tests that validate that a set of expectations are met.
The usual layout::

	project/
	|-library.py
	|-test/
	  |-test_library.py

Where `test_lib.py` contains a set of functions prefixed with ``test_``::

   def test_feature1(test):
      ...

   def test_feature2(test):
      ...

The methods on the `test` object given to these functions provides the logic
to be performed and the failure mechanism to employ when an expectation is not
met. Details about the available methods can be found in the
:py:mod:`.libtest` module's reference documentation.

Executing Tests
---------------

Currently, :py:mod:`.libtest` only supports *developer execution*. This is
simply making the test module executable using::

   if __name__ == '__main__':
      from dev import libtest
      import sys; libtest.execute(sys.modules[__name__])

@libtest.execute is a bare-metal means to perform test
execution, and failures unconditionally trigger the debugger. It is intended
strictly for interactive use during the development of a module.
