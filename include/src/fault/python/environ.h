/**
	# Python C-API extensions for compensating for older versions
	# and for providing additional utility.
*/
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>
#include <pythread.h>

#define PYTHON_MODULE_PATH_STR (STRING_FROM_IDENTIFIER(FACTOR_PROJECT) "." STRING_FROM_IDENTIFIER(FACTOR_SUBPATH))

typedef PyObject * PyObj;

#if FV_INJECTIONS()
	extern PyObj __ERRNO_RECEPTACLE__;
	extern PyObj __PYTHON_RECEPTACLE__;
#endif

/**
	# Cover in case of absence
*/
#ifndef Py_RETURN_NONE
	#define Py_RETURN_NONE do { Py_INCREF(Py_None); return(Py_None); } while(0)
#endif

#define PyAllocate(TYP) (((PyTypeObject *) TYP)->tp_alloc((PyTypeObject *) TYP, 0))

#define PYMETHOD(name, func, args, doc) {#name, (PyCFunction) func, args, PyDoc_STR(doc)},

static inline PyObj
_PyLoop_DictionaryItems(PyObj d)
{
	PyObj iterable, iterator;
	iterable = PyDict_Items(d);
	iterator = PyObject_GetIter(iterable);
	Py_DECREF(iterable);
	return(iterator);
}

extern PyObj __dict__;

static inline PyObj
PyImport_ImportAdjacent(const char *modname, const char *attribute)
{
	PyObj is_m, is_ob, is_fromlist;

	is_fromlist = Py_BuildValue("(s)", attribute);
	if (is_fromlist == NULL)
		return(NULL);

   is_m = PyImport_ImportModuleLevel(modname, __dict__, __dict__, is_fromlist, 1);

	Py_DECREF(is_fromlist);
	if (is_m == NULL)
		return(NULL);

	is_ob = PyObject_GetAttrString(is_m, attribute);
	Py_DECREF(is_m);

	return(is_ob);
}
#define import_sibling PyImport_ImportAdjacent

#define _PyLoop_Error(ITER) goto _PYERR_LABEL_##ITER
#define _PyLoop_PassThrough(ITEM, OUTPUT, ...) ((*(OUTPUT) = ITEM) ? NULL : NULL)
#define _PyLoop_NULL_INJECTION() ;
#define PyLoop_ITEM _ITEM

#define _PyLoop_Iterator(INJECTION, CONVERT_SUCCESS, CONVERT, GETITER, ITER, ...) \
{ \
	PyObj _ITER = NULL; \
	PyObj _PyLoop_ITEM = NULL; \
	\
	INJECTION() \
	\
	_ITER = GETITER(ITER); \
	if (_ITER == NULL) \
		_PyLoop_Error(ITER); \
	else \
	{ \
		while ((_PyLoop_ITEM = PyIter_Next(_ITER)) != NULL) \
		{ \
			if (CONVERT(_PyLoop_ITEM, __VA_ARGS__) != CONVERT_SUCCESS) \
			{ \
				Py_XDECREF(_PyLoop_ITEM); \
				_PyLoop_ITEM = NULL; \
				Py_XDECREF(_ITER); \
				_ITER = NULL; \
				_PyLoop_Error(ITER); \
			} \


			#define PyLoop_CatchError(ITER) \
			Py_DECREF(_PyLoop_ITEM); \
		} \
		\
		Py_XDECREF(_PyLoop_ITEM); \
		_PyLoop_ITEM = NULL; \
		Py_XDECREF(_ITER); \
		_ITER = NULL; \
	} \
	\
	if (PyErr_Occurred()) \
	{ \
		_PYERR_LABEL_##ITER: \


		#define PyLoop_End(ITER) \
	} \
}

/*
 * PyLoop_ForEach(iter, &obj)
 * {
 *     ...
 * }
 * PyLoop_CatchError(iter)
 * {
 *     ...
 * }
 * PyLoop_End(iter)
 */

#define PyLoop_ForEachTuple(ITER, ...) \
	_PyLoop_Iterator(_PyLoop_NULL_INJECTION, 1, PyArg_ParseTuple, PyObject_GetIter, ITER, __VA_ARGS__)
#define PyLoop_ForEachDictItem(DICT, ...) \
	_PyLoop_Iterator(_PyLoop_NULL_INJECTION, 1, PyArg_ParseTuple, _PyLoop_DictionaryItems, DICT, __VA_ARGS__)

/* For Each item in iterator loop with no conversion. */
#define PyLoop_ForEach(ITER, ...) \
	_PyLoop_Iterator(_PyLoop_NULL_INJECTION, NULL, _PyLoop_PassThrough, PyObject_GetIter, ITER, __VA_ARGS__)
