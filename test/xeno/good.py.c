/*
 * good.py.c - test library for the c loader
 */
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

PyDoc_STRVAR(kind_doc,
"Kind()\n\n"
"\n"
"Example Type\n"
);

struct Kind {
	PyObject_HEAD
};
PyTypeObject KindType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	QPATH("Kind"),					/* tp_name */
	sizeof(struct Kind),			/* tp_basicsize */
	0,									/* tp_itemsize */
	NULL,								/* tp_dealloc */
	NULL,								/* tp_print */
	NULL,								/* tp_getattr */
	NULL,								/* tp_setattr */
	NULL,								/* tp_compare */
	NULL,								/* tp_repr */
	NULL,								/* tp_as_number */
	NULL,								/* tp_as_sequence */
	NULL,								/* tp_as_mapping */
	NULL,								/* tp_hash */
	NULL,								/* tp_call */
	NULL,								/* tp_str */
	NULL,								/* tp_getattro */
	NULL,								/* tp_setattro */
	NULL,								/* tp_as_buffer */
	Py_TPFLAGS_DEFAULT,			/* tp_flags */
	kind_doc,						/* tp_doc */
	NULL,								/* tp_traverse */
	NULL,								/* tp_clear */
	NULL,								/* tp_richcompare */
	0,									/* tp_weaklistoffset */
	NULL,								/* tp_iter */
	NULL,								/* tp_iternext */
	NULL,								/* tp_methods */
	NULL,								/* tp_members */
	NULL,								/* tp_getset */
	NULL,								/* tp_base */
	NULL,								/* tp_dict */
	NULL,								/* tp_descr_get */
	NULL,								/* tp_descr_set */
	0,									/* tp_dictoffset */
	NULL,								/* tp_init */
	NULL,								/* tp_alloc */
	NULL,								/* tp_new */
};

INIT(PyDoc_STR("good docs"))
{
	PyObj mod;
	CREATE_MODULE(&mod);

	PyType_Ready(&KindType);
	PyModule_AddObject(mod, "Kind", (PyObject *) &KindType);

	return(mod);
}
/*
 * vim: ts=3:sw=3:noet:
 */
