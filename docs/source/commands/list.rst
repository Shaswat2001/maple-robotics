====
list
====

List pulled policies and environments.

Synopsis
========

.. code-block:: bash

   maple list policy [OPTIONS]
   maple list env [OPTIONS]

list policy
===========

List all pulled policies.

.. code-block:: bash

   maple list policy [OPTIONS]

Options
-------

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)

Example
-------

.. code-block:: bash

   maple list policy

Output:

.. code-block:: text

   Pulled policies:
     • openvla:7b
     • smolvla:libero

list env
========

List all pulled environments.

.. code-block:: bash

   maple list env [OPTIONS]

Options
-------

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)

Example
-------

.. code-block:: bash

   maple list env

Output:

.. code-block:: text

   Pulled environments:
     • libero
     • simplerenv

See Also
========

- ``maple status`` — Show running policies/environments
