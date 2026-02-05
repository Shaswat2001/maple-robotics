======
remove
======

Remove policies and environments from the system.

Synopsis
========

.. code-block:: bash

   maple remove policy NAME [OPTIONS]
   maple remove env NAME [OPTIONS]

Description
===========

The ``remove`` command group provides clean resource deletion functionality:

- **Remove policies**: Delete policy models, weights, and stop containers
- **Remove environments**: Delete environments, Docker images, and stop containers

Unlike manually deleting files, ``remove`` ensures:

1. Running containers are stopped first
2. Database entries are cleaned up
3. Files/images are properly deleted
4. No orphaned resources remain

Policy Mode
===========

Remove a policy model from the system:

.. code-block:: bash

   maple remove policy NAME [OPTIONS]

Arguments
---------

``NAME``
    Policy name (e.g., ``openvla:7b``)

Options
-------

``--keep-weights``
    Keep model weights on disk (only remove image and policy from database)

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)

Examples
--------

.. code-block:: bash

   # Remove with confirmation
   maple remove policy openvla:7b

   # Remove but keep weights on disk
   maple remove policy openvla:7b --keep-weights

Output
------

.. code-block:: text

   The following will be removed:
     Policy: openvla:7b
     Database entry: Yes
     Weights path: /home/user/.maple/models/openvla/7b
      
   Stopping policy container: openvla-7b-abc123
   ✓ Removed from database
   ✓ Deleted weights from /home/user/.maple/models/openvla/7b

Environment Mode
================

Remove an environment from the system:

.. code-block:: bash

   maple remove env NAME [OPTIONS]

Arguments
---------

``NAME``
    Environment name (e.g., ``libero``, ``simplerenv``)

Options
-------

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)

Examples
--------

.. code-block:: bash

   # Remove with confirmation
   maple remove env libero

Output
------

.. code-block:: text

   The following will be removed:
     Environment: libero
     Database entry: Yes
     Docker image: maple/libero:latest
   
   Stopping environment container: libero-x1y2z3w4
   ✓ Removed from database
   ✓ Deleted Docker image

Notes
=====

Safety Features
---------------

- **Container stopping**: Running containers are automatically stopped before removal

Error Handling
--------------

**Non-existent resources**:

.. code-block:: text

   Error: Policy openvla:7b not found in database

**Docker errors**:

.. code-block:: text

   Warning: Could not check for running containers: ...
   ✓ Removed from database
   Error removing Docker image: Cannot connect to Docker daemon

**Permission errors**:

.. code-block:: text

   ✓ Removed from database
   Error deleting weights: Permission denied

See Also
========

- :doc:`sync` - Sync database with manually deleted resources
- :doc:`pull` - Download policies and environments
- :doc:`serve` - Start containers
- :doc:`list` - List available resources