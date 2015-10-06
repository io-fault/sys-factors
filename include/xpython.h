/* Extended Python C-APIs */
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
