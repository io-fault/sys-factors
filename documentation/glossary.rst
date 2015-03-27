Glossary
========

.. glossary::
 :sorted:

 Fate
  The result of a test. Normally, Pass or Fail.

 Focus
  The test subject. The callable that is passed the @abstract.Test instance
  used to control the fate.

 Project
  The root package that makes up a package. Denoted by the presence of a
  :py:attr:`__pkg_bottom__` field in the root package module.

 Context Package
  A Python package containing a set of Projects. A Context Package is likely a Project as
  well, but is usually referred to a a Context Package.
