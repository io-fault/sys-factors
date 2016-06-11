/*
 * Support for failure injection.
 */
#if TEST() || METRICS()
extern PyObj __ERRNO_RECEPTACLE__;
extern PyObj __PYTHON_RECEPTACLE__;

/*
 * Reclaiming the GIL is rather time consuming in some contexts,
 * so if the dictionary is zero, don't bother.
 *
 * ERRNO_RECEPTACLE(0, &r, open, ...)
 * if (r == 0)
 * {
 *
 * }
 */
#define ERRNO_RECEPTACLE(ERROR_STATUS, RETURN, SYSCALL, ...) \
do { \
	PyObj _er_entry; \
	PyGILState_STATE _er_gs; \
	if (PyDict_Size(__ERRNO_RECEPTACLE__) == 0) \
	{ \
		*(RETURN) = SYSCALL(__VA_ARGS__); \
	} \
	else \
	{ \
		char _er_name[256]; \
		snprintf(_er_name, 256, "%s.%s", __func__, #SYSCALL); \
		_er_gs = PyGILState_Ensure(); /* need it to get the item */ \
		_er_entry = PyDict_GetItemString(__ERRNO_RECEPTACLE__, (char *) _er_name); \
		\
		if (_er_entry == NULL) \
		{ \
			*(RETURN) = SYSCALL(__VA_ARGS__); \
		} \
		else \
		{ \
			PyObj _er_override = PyObject_CallFunction(_er_entry, "ss", (char *) __func__, #SYSCALL); \
			\
			if (_er_override == Py_False) \
			{ \
				/* dont override and perform syscall */ \
				*(RETURN) = SYSCALL(__VA_ARGS__); \
			} \
			else \
			{ \
				/* overridden */ \
				int seterrno = -1; \
				if (_er_override == NULL || !PyArg_ParseTuple(_er_override, "i", &seterrno)) \
				{ \
					/* convert to python warning */ \
					PyErr_Clear(); \
					fprintf(stderr, \
						"errno injections must return tuples of '%s' OR False: %s.%s\n", \
						"i", (char *) __func__, #SYSCALL); \
				} \
				/* injected errno */ \
				errno = seterrno; \
				*(RETURN) = ERROR_STATUS; \
			} \
			\
			Py_XDECREF(_er_override); \
		} \
		PyGILState_Release(_er_gs); \
	} \
} while(0)

/*
 * Usually called with GIL. Dynamically override a C-API call.
 */
#define PYTHON_RECEPTACLE(ID, RETURN, CALL, ...) \
do { \
	PyObj _pr_entry; \
	if (PyDict_Size(__PYTHON_RECEPTACLE__) == 0) \
	{ \
		*((PyObj *) RETURN) = (PyObj) CALL(__VA_ARGS__); \
	} \
	else \
	{ \
		char _er_name[256]; \
		snprintf(_er_name, 256, "%s.%s", __func__, #ID); \
		_pr_entry = PyDict_GetItemString(__PYTHON_RECEPTACLE__, (char *) _er_name); \
		if (_pr_entry == NULL) \
		{ \
			*((PyObj *) RETURN) = (PyObj) CALL(__VA_ARGS__); \
		} \
		else \
		{ \
			PyObj _pr_override = PyObject_CallFunction(_pr_entry, "s", #CALL); \
			if (_pr_override == Py_False) \
			{ \
				Py_DECREF(_pr_override); \
				*((PyObj *) RETURN) = (PyObj) CALL(__VA_ARGS__); \
			} \
			else if (_pr_override != NULL) \
			{ \
				/* overridden */ \
				if (!PyArg_ParseTuple(_pr_override, "(O)", RETURN)) \
				{ \
					*(RETURN) = NULL; \
				} \
			} \
			else \
			{ \
				*(RETURN) = NULL; \
			} \
		} \
	} \
} while(0)

#else
	#define ERRNO_RECEPTACLE(ERROR_STATUS, RETURN, SYSCALL, ...) \
		*(RETURN) = SYSCALL(__VA_ARGS__)

	#define PYTHON_RECEPTACLE(ID, RETURN, CALL, ...) \
		*((PyObj *) RETURN) = (PyObj) CALL(__VA_ARGS__)
#endif
