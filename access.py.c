#if TEST()
void __gcov_flush(void);

static PyObj
flush_measurements(PyObj self)
{
	__gcov_flush();
	Py_RETURN_NONE;
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
		PyDoc_STR("call to flush any collected test related data")},
	{NULL},
};

INIT("")
{
	PyObj mod;
	CREATE_MODULE(&mod);
	return(mod);
}
