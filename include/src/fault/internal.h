/*
 * Imported before *target* local includes and public function definitions.
 * For some platforms, this selects the SYMBOL() implementation
 * that exports symbols for referencing by other libraries or executables.
 */
#include "symbols.h"

#ifdef SYMBOL
	#undef SYMBOL
#endif

#define SYMBOL(...) _fault_reveal_symbol __VA_ARGS__
