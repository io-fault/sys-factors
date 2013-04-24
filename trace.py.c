#include <sys/types.h>
#include <sys/time.h>
#include <frameobject.h>

struct Collector {
	PyObject_HEAD
	PyObj col_queue_op; /* cached col_queue.append */
	PyObj col_delta_op; /* time tracking */
};
typedef struct Collector *Collector;

static PyObj event_objects[7]; /* n-event types */

static PyObj
trace(PyObj self, PyFrameObject *f, int what, PyObj arg)
{
	Collector col = (Collector) self;
	PyObj append;
	PyCodeObject *code;
	PyObj rob, item;
	PyObj event, tdelta, firstlineno = NULL, lineno = NULL;
	PyObj module_name, class_name = NULL, name, filename;

	code = f->f_code;
	name = code->co_name;
	filename = code->co_filename;
	event = event_objects[what];

	tdelta = PyObject_CallObject(col->col_delta_op, NULL);
	if (tdelta == NULL)
		return(NULL);

	lineno = PyLong_FromLong((long) f->f_lineno);
	if (lineno == NULL)
		goto error;

	firstlineno = PyLong_FromLong((long) code->co_firstlineno);
	if (firstlineno == NULL)
		goto error;

	module_name = PyMapping_GetItemString(f->f_globals, "__name__");
	if (module_name == NULL)
		goto error;

	if (code->co_argcount > 0)
	{
		PyObj first = PySequence_GetItem(code->co_varnames, 0);
		if (first == NULL)
		{
			PyErr_Clear();
			class_name = Py_None;
			Py_INCREF(class_name);
		}
		else
		{
			switch (PyMapping_HasKey(f->f_locals, first))
			{
				case -1:
					PyErr_Clear();
				case 0:
					Py_DECREF(first);
					class_name = Py_None;
					Py_INCREF(class_name);
				break;

				case 1:
					class_name = PyObject_GetItem(f->f_locals, first);
					Py_DECREF(first);
					if (class_name == NULL)
					{
						PyErr_Clear();
						class_name = Py_None;
						Py_INCREF(class_name);
					}
				break;
			}
		}
	}
	else
	{
		class_name = Py_None;
		Py_INCREF(class_name);
	}

	item = PyTuple_New(9);
	if (item == NULL)
		goto error;

	PyTuple_SET_ITEM(item, 0, module_name);
	PyTuple_SET_ITEM(item, 1, class_name);
	Py_INCREF(Py_None);
	PyTuple_SET_ITEM(item, 2, filename);
	Py_INCREF(filename);

	PyTuple_SET_ITEM(item, 3, firstlineno);
	PyTuple_SET_ITEM(item, 4, lineno);

	PyTuple_SET_ITEM(item, 5, name);
	Py_INCREF(name);

	PyTuple_SET_ITEM(item, 6, event);
	Py_INCREF(event);
	if (arg == NULL)
		arg = Py_None;
	PyTuple_SET_ITEM(item, 7, arg);
	Py_INCREF(arg);
	PyTuple_SET_ITEM(item, 8, tdelta);

	rob = PyObject_CallFunction(col->col_queue_op, "(O)", item);
	Py_DECREF(item);

	if (rob == NULL)
		return(-1);
	else
	{
		Py_DECREF(rob);
	}

	return(0);

error:
	Py_XDECREF(firstlineno);
	Py_XDECREF(lineno);
	return(-1);
}

static PyMemberDef
collector_members[] = {
	{"endpoint", T_OBJECT, offsetof(struct Collector, col_queue_op), READONLY, PyDoc_STR("the operation ran to record the event")},
	{"delta", T_OBJECT, offsetof(struct Collector, col_delta_op), READONLY, PyDoc_STR("the time delta operation to use")},
	{NULL,},
};

static PyObj
collector_install(PyObj self)
{
	PyEval_SetTrace(trace, self);
	Py_RETURN_NONE;
}

static PyMethodDef
collector_methods[] = {
	{"install", collector_install, METH_NOARGS, PyDoc_STR("Install the collector for the thread. One collector per-thread.")},
	{NULL},
};

static void
collector_dealloc(PyObj self)
{
	Collector col = (Collector) self;

	Py_DECREF(col->col_queue_op);
	Py_DECREF(col->col_delta_op);
}

static PyObj
collector_new(PyTypeObject *subtype, PyObj args, PyObj kw)
{
	static char *kwlist[] = {"queue", "time_delta", NULL};
	Collector col;
	PyObj top, qop = NULL;
	PyObj rob;

	if (!PyArg_ParseTupleAndKeywords(args, kw, "OO", kwlist, &qop, &top))
		return(NULL);

	rob = PyAllocate(subtype);
	if (rob == NULL)
		return(NULL);

	col = (Collector) rob;

	col->col_queue_op = qop;
	Py_INCREF(qop);

	col->col_delta_op = top;
	Py_INCREF(top);

	return(rob);
}

#define FRAME_INDEX 0
#define EVENT_INDEX 1
#define ARG_INDEX 2

static PyObj
collector_call(PyObj self, PyObj args, PyObj kw)
{
	Collector col = (Collector) self;
	PyObj append;
	PyFrameObject *f;
	PyObj rob, item;
	PyObj event, arg;

	if (PyTuple_GET_SIZE(args) != 3)
	{
		PyErr_SetString(PyExc_ValueError, "collector requires three arguments");
		return(NULL);
	}

	if (kw != NULL)
	{
		PyErr_SetString(PyExc_ValueError, "collector does not accept keyword arguments");
		return(NULL);
	}

	f = (PyFrameObject *) PyTuple_GET_ITEM(args, FRAME_INDEX);
	event = PyTuple_GET_ITEM(args, EVENT_INDEX);
	arg = PyTuple_GET_ITEM(args, ARG_INDEX);

	return(trace(self, f, 0, arg));
}

const char collector_doc[] = "A callable object that manages the collection of trace events for later aggregation";

PyTypeObject
CollectorType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	QPATH("Collector"),				/* tp_name */
	sizeof(struct Collector),		/* tp_basicsize */
	0,										/* tp_itemsize */
	NULL,									/* tp_dealloc */
	NULL,									/* tp_print */
	NULL,									/* tp_getattr */
	NULL,									/* tp_setattr */
	NULL,									/* tp_compare */
	NULL,									/* tp_repr */
	NULL,									/* tp_as_number */
	NULL,									/* tp_as_sequence */
	NULL,									/* tp_as_mapping */
	NULL,									/* tp_hash */
	collector_call,					/* tp_call */
	NULL,									/* tp_str */
	NULL,									/* tp_getattro */
	NULL,									/* tp_setattro */
	NULL,									/* tp_as_buffer */
	Py_TPFLAGS_BASETYPE|
	Py_TPFLAGS_DEFAULT,				/* tp_flags */
	collector_doc,						/* tp_doc */
	NULL,									/* tp_traverse */
	NULL,									/* tp_clear */
	NULL,									/* tp_richcompare */
	0,										/* tp_weaklistoffset */
	NULL,									/* tp_iter */
	NULL,									/* tp_iternext */
	collector_methods,				/* tp_methods */
	collector_members,				/* tp_members */
	NULL,									/* tp_getset */
	NULL,									/* tp_base */
	NULL,									/* tp_dict */
	NULL,									/* tp_descr_get */
	NULL,									/* tp_descr_set */
	0,										/* tp_dictoffset */
	NULL,									/* tp_init */
	NULL,									/* tp_alloc */
	collector_new,						/* tp_new */
};

/* METH_O, METH_VARARGS, METH_VARKEYWORDS, METH_NOARGS */
METHODS() = {
	{NULL}
};

INIT("C-Level trace support")
{
	PyObj mod;

	CREATE_MODULE(&mod);

	if (PyType_Ready(&CollectorType) != 0)
		goto fail;
	PyModule_AddObject(mod, "Collector", (PyObj) (&CollectorType));

	PyModule_AddIntConstant(mod, "TRACE_CALL", PyTrace_CALL);
	PyModule_AddIntConstant(mod, "TRACE_EXCEPTION", PyTrace_EXCEPTION);
	PyModule_AddIntConstant(mod, "TRACE_RETURN", PyTrace_RETURN);

	PyModule_AddIntConstant(mod, "TRACE_LINE", PyTrace_LINE);

	PyModule_AddIntConstant(mod, "TRACE_C_CALL", PyTrace_C_CALL);
	PyModule_AddIntConstant(mod, "TRACE_C_EXCEPTION", PyTrace_C_EXCEPTION);
	PyModule_AddIntConstant(mod, "TRACE_C_RETURN", PyTrace_C_RETURN);

	event_objects[PyTrace_CALL]			= PyDict_GetItemString(__dict__, "TRACE_CALL");
	event_objects[PyTrace_EXCEPTION]		= PyDict_GetItemString(__dict__, "TRACE_EXCEPTION");
	event_objects[PyTrace_LINE]			= PyDict_GetItemString(__dict__, "TRACE_LINE");
	event_objects[PyTrace_RETURN]			= PyDict_GetItemString(__dict__, "TRACE_RETURN");

	event_objects[PyTrace_C_CALL]			= PyDict_GetItemString(__dict__, "TRACE_C_CALL");
	event_objects[PyTrace_C_EXCEPTION]	= PyDict_GetItemString(__dict__, "TRACE_C_EXCEPTION");
	event_objects[PyTrace_C_RETURN]		= PyDict_GetItemString(__dict__, "TRACE_C_RETURN");

	Py_INCREF(event_objects[PyTrace_CALL]);
	Py_INCREF(event_objects[PyTrace_EXCEPTION]);
	Py_INCREF(event_objects[PyTrace_LINE]);
	Py_INCREF(event_objects[PyTrace_RETURN]);
	Py_INCREF(event_objects[PyTrace_C_CALL]);
	Py_INCREF(event_objects[PyTrace_C_EXCEPTION]);
	Py_INCREF(event_objects[PyTrace_C_RETURN]);

	return(mod);
fail:
	DROP_MODULE(mod);
	return(NULL);
}
/*
 * vim: ts=3:sw=3:noet:
 */
