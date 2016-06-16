"""
Test compilation of system modules.
"""
from .. import libfactor as library

# Temporary directories are used to manage
# the test compilation modules.
from ...routes import library as libroutes

bad_c_module = \
	"""
	/* Should never compile successfully. */
	#include <Pythonnn.h>

	static PyMethodDef methods[] = {
		{NULL}

	xxxx

	INIT()
	{
		PyObject *mod;
		mod = PyModule_Create(&module);
		return(mod);
	}
	"""

good_cxx_module = \
	"""
	namespace bar {
		bool foofoo = true;
	}

	static PyObj
	return_true(PyObject *self)
	{
		PyObj rob;

		if (bar::foofoo)
			rob = Py_True;
		else
			rob = Py_False;

		Py_INCREF(rob);
		return(rob);
	}

	/* METH_O, METH_VARARGS, METH_VARKEYWORDS, METH_NOARGS */
	METHODS() = {
		{"return_true", (PyCFunction) return_true, METH_NOARGS, "return `True`"},
		{NULL}
	};

	INIT(PyDoc_STR("cxx docs"))
	{
		PyObj mod;

		CREATE_MODULE(&mod);
		if (mod == NULL)
			return(NULL);

		return(mod);
	}
	"""

good_objc_module = \
	"""
	#import "CoreFoundation/CoreFoundation.h"
	#import "Foundation/NSString.h"
	#import "Foundation/NSAutoreleasePool.h"

	static PyObject *
	return_true(PyObject *self)
	{
		Py_INCREF(Py_True);
		return(Py_True);
	}

	/* METH_O, METH_VARARGS, METH_VARKEYWORDS, METH_NOARGS */
	METHODS() = {
		{"return_true", (PyCFunction) return_true, METH_NOARGS, "return `True`"},
		{NULL}
	};

	INIT(PyDoc_STR("objc docs"))
	{
		NSAutoreleasePool *pool;
		NSString *str;
		PyObj mod;

		CREATE_MODULE(&mod);
		if (mod == NULL)
			return(NULL);

		pool = [[NSAutoreleasePool alloc] init];
		str = [NSString stringWithUTF8String: "foobar"];

		PyModule_AddIntConstant(mod, "foobarhash", (long) [str hash]);
		[pool drain];
		return(mod);
	}
	"""

good_probe_module = \
	"""
	static PyObject *
	return_true(PyObject *self)
	{
		Py_INCREF(Py_True);
		return(Py_True);
	}

	static PyObject *
	return_foo(PyObject *self)
	{
		return(PyUnicode_FromString(foo));
	}

	/* METH_O, METH_VARARGS, METH_VARKEYWORDS, METH_NOARGS */
	METHODS() = {
		{"return_true", (PyCFunction) return_true, METH_NOARGS, "return `True`"},
		{"return_foo", (PyCFunction) return_foo, METH_NOARGS, "return a define set by the c.probed.render_stack()"},
		{NULL}
	};

	INIT(PyDoc_STR("docs!"))
	{
		PyObj mod;
		CREATE_MODULE(&mod);
		return(mod);
	}
	"""

trace_module = \
	"""
	#include <Python.h>
	#include <structmember.h>

	/* METH_O, METH_VARARGS, METH_VARKEYWORDS, METH_NOARGS */
	METHODS() = {
		{NULL}
	};

	INIT("")
	{
		PyObj mod;
		CREATE_MODULE(&mod);
		return(mod);
	}
	"""

def test_roles_management(test):
	# defaults to factor
	test/library.role('void') == 'optimal'
	test/library.role('void.module') == 'optimal'

	# override default for everything in void.
	library.select('void.', 'debug')
	test/library.role('void') == 'debug'
	test/library.role('void.module') == 'debug'

	# designate exact
	library.select('void.alternate', 'test')
	test/library.role('void.alternate') == 'test'

if __name__ == '__main__':
	from .. import libtest; import sys
	libtest.execute(sys.modules[__name__])
