/*
 * cxx_good.py.cxx - test cxx imports
 */
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
/*
 * vim: ts=3:sw=3:noet:
 */
