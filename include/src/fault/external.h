/*
 * Imported before fault-aware dependency headers that may need their
 * interfaces to be identified as imports on some platforms (windows).
 */
#include "symbols.h"

#ifdef SYMBOL
	#undef SYMBOL
#endif
#define SYMBOL(...) _fault_request_symbol __VA_ARGS__
