#include <fault/roles.h>
#include <fault/python/environ.h>
#include <fault/python/module.h>

#if TEST()
/*
 * Symbol won't be available without TEST()
 */
void __gcov_flush(void);

static PyObj
flush_measurements(PyObj self)
{
	__gcov_flush();
	Py_INCREF(Py_True);
	return(Py_True);
}
#else
static PyObj
flush_measurements(PyObj self)
{
	Py_RETURN_NONE;
}
#endif

METHODS() = {
	{"flush_measurements",
		(PyCFunction) flush_measurements, METH_NOARGS,
		PyDoc_STR("call to flush any collected coverage and profiling data")},
	{NULL},
};

INIT("access to coverage controls")
{
	PyObj mod;
	CREATE_MODULE(&mod);
	return(mod);
}
