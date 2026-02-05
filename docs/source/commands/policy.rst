======
policy
======

Policy-related operations.

Synopsis
========

.. code-block:: bash

   maple policy info POLICY_ID [OPTIONS]
   maple policy stop POLICY_ID [OPTIONS]

Subcommands
===========

info
----

Get information about the policy in the container.

.. code-block:: bash

   maple policy info POLICY_ID [OPTIONS]

Arguments
^^^^^^^^^

``POLICY_ID``
    ID of running policy

Options
^^^^^^^

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)

Example
^^^^^^^

.. code-block:: bash

   maple policy info openvla-7b-abc123

Output:

.. code-block:: text

   Policy Info:
    Name: openvla
    Loaded: True
    Model Path: /models/openvla
    Device: cpu
    Image Size: [224, 224]
   
stop
----

Stop a running policy container.

.. code-block:: bash

   maple policy stop POLICY_ID [OPTIONS]

Arguments
^^^^^^^^^

``POLICY_ID``
    ID of policy to stop

Options
^^^^^^^

``--port INTEGER``
    Daemon port

Example
^^^^^^^

.. code-block:: bash

   maple policy stop openvla-7b-abc123

Output:

.. code-block:: text

   ✓ Stopped: openvla-7b-abc123
