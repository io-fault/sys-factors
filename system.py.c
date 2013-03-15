/*
 * dev.system.py.c - access to system calls primarily used in development
 */
static PyObject *
system_abort(PyObject *self)
{
	abort();
	PyErr_SetString(PyExc_RuntimeError, "process did not abort");
	return(NULL);
}

METHODS() = {
	{"abort", (PyCFunction) system_abort, METH_NOARGS, "Causes the process to abort, potentially, leaving a coredump."},
	{NULL}
};

INIT("C-API Access to the System")
{
	return(PyModule_Create(&module));
}
/*
 * vim: ts=3:sw=3:noet:
 */
