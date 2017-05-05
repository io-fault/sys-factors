"""
# Report grammar for serializing profile and coverage data.

# The grammar is designed for formatting making XSLT processing as easy as possible.
# This is nearly a direct mapping to row data for populating table elements.
# The primary distinguishing factor is the explicit separation of measurements and
# dimensions. This is done to simplify the acceptance of ordering parameters
# to XSL transformations.
"""
__factor_domain__ = 'xml'
__factor_type__ = 'executable'
