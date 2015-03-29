/*
 * objc_good.py.c - test library for the c loader
 */
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
/*
 * vim: ts=3:sw=3:noet:
 */
