/*
 * probed.py.c - test library for the c loader that uses probes
 */

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
/*
 * vim: ts=3:sw=3:noet:
 */
