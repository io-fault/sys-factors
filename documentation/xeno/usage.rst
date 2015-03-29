=====
Usage
=====

This chapter describes how to use project in a linear fashion.

Loader Initialization
=====================

In order for `xeno` to be enabled, it's loader must be added to the system's metapath
list. With a default Python implementation, :py:mod:`zeno.loader` is not imported and
its loader is not added to the list.

There are two recommended ways to manage the xeno loader: global pth-file installation
and subpackaging. Subpackaging is the preferred method as it allows easy parameterization
of module renders. The pth-file method is useful for supporting colloquial packaging
styles.

Subpackaging
------------

Subpackaging `xeno` is a great way to limit the scope of the laoder. Subsequently, this
makes customization easier as well. Subpackaging xeno means to install the `xeno` package
module as a subpackage in your project. An SCM submodule inside your root package module
usually suffices. Subsequently, the root package module, ``__init__.py``, should contain
the following lines::

   __pkg_bottom__ = True
   from .xeno import loader
   loader.install()
   del loader
   xeno.__pkg_bottom__ = False # limits loader's scope

This causes the loader to be installed the moment the root package module is imported. The
root package module *will* be imported before any of its C-API submodules.

Subpackaging is preferred as the xeno loader will only apply itself to modules that exist
within the root package module. Subsequently, the compilation environment can be tailored
to the root package's use case.

pth-file Initialization
-----------------------

xeno can be initialized using a pth-file. This is the method setuptools used to make
egg-files importable.

The '.pth' file can be created by running the following::

   python3 -c 'import xeno.loader as x; x.autoload()'

Without this, Python applications depending on `xeno` will have to explicitly import
and install the loader::

   import xeno.loader
   xeno.loader.install()

Explicit installation is preferred in subpackaging contexts.

Importing C-API Extension Modules
=================================

After `xeno` is installed, C-API extension modules can be directly imported::

	import root_pkg.my_c_mod

Where the file :file:`root_pkg/my_c_mod.py.c` exists in the Python `sys.path`.

.. note::   It is *necessary* for the user to have write privileges to the __pycache__ directory
            associated with the module's location.

If compilation of `my_c_mod` fails, an `ImportError` will be raised chained to a
:py:class:`.lib.ToolError` with the output of the stage that it failed on--compilation
or linkage, normally.

Preprocessor Environment
------------------------

:project:`xeon` provides a set of macros and defines that provide abstractions and
information about the context that the extension module is being compiled under. These
macros help to make the C-API module portable and relocatable.

Objective-C Environment
-----------------------

In order to work with Objective-C, objects often need to be converted to and from common
NSObject types.

Reading the Compilation Transcript
==================================

Compilation is often associated with a lot of information about the process.
Notably, warnings are often present in compiler output. However, the loader
does not allow this detail to be printed to the terminal. This is desirable as
it is inappropriate for the import machinery to emit such noise. To compensate,
relevant information about the compilation process is recorded to a log file
alongside the compiled output. This output can be viewed using the
:py:mod:`xeno.bin.log` executable module::

	python3 -m xeno.bin.log package.my_c_mod

Probing the Environment
=======================

Often, C-API extensions need to probe the environment in order to select the appropriate
dependency for their functionality. This is the job that common `configure` perform. With
xeno, compilation occurs on import so probing has to occur during import as well.
