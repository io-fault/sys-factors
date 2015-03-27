/*
 * Extended Python C-APIs
 */
#define _PyLoop_Error(ITER) goto _PYERR_LABEL_##ITER
#define _PyLoop_NULL_INJECTION() ;
#define PyLoop_ITEM _ITEM

#define _PyLoop_Iterator(INJECTION, CONVERT_SUCCESS, CONVERT, ITER, GETITER, ...) \
{ \
	PyObj _ITER = NULL; \
	PyObj PyLoop_ITEM; \
\
	INJECTION() \
\
	_ITER = GETITER(ITER); \
	if (_ITER == NULL) \
		_PyLoop_Error(ITER); \
	else \
	{ \
		while ((PyLoop_ITEM = PyIter_Next(_ITER)) != NULL) \
		{ \
			if (CONVERT(PyLoop_ITEM, __VA_ARGS__) != CONVERT_SUCCESS) \
			{ \
				Py_XDECREF(PyLoop_ITEM); \
				_PyLoop_Error(ITER); \
			} \

#define PyLoop_CatchError(ITER) \
			Py_DECREF(PyLoop_ITEM); \
		} \
		Py_XDECREF(PyLoop_ITEM); \
		PyLoop_ITEM = NULL; \
	} \
\
	_PYERR_LABEL_##ITER: \
	if (PyErr_Occurred()) \
	{ \

#define PyLoop_End(ITER) \
	} \
}

#define PyLoop_ForEachTuple(ITER, ...) \
	_PyLoop_Iterator(_PyLoop_NULL_INJECTION, 0, PyArg_ParseTuple, ITER, PyObject_GetIter, __VA_ARGS__)
#define PyLoop_ForEachDictItem(DICT, ...) \
	_PyLoop_Iterator(_PyLoop_NULL_INJECTION, 0, PyArg_ParseTuple, DICT, PyDict_Items, __VA_ARGS__)
