"""
Structure
=

The structure of the project. Prevalent high-level concepts.
Where such concepts are manifested.

Requirements
=

Any hidden dependencies or notes about dependencies.

Defense
=

Defend your project's existence, but only defend modules that are intended for
external use.
"""
abstract = 'single sentence description of project'

#: Project name.
name = 'skeleton'

#: The name of the conceptual branch of development.
fork = 'ghostly' # Explicit branch name and a codename for the major version of the project.
release = None # A number indicating its position in the releases of a branch. (fork)

#: The particular study or subject that the package is related to.
study = {}

#: Relevant emoji or reference--URL or relative file path--to an image file.
icon = '👻'

#: IRI based project identity. (project homepage)
identity = 'URL uniquely identifying the project.'

#: Responsible Party
controller = 'Your Name or Organization'

#: Contact point for the Responsible Party
contact = 'mailto:x'

#: Version tuple: (major, minor, patch)
version_info = (0, 1, 0)

#: The version string.
version = '.'.join(map(str, version_info))
