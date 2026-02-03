======
policy
======

Policy-related operations.

Synopsis
========

.. code-block:: bash

   maple policy act POLICY_ID --image PATH --instruction TEXT [OPTIONS]
   maple policy stop POLICY_ID [OPTIONS]

Subcommands
===========

act
---

Get action from policy for a single observation.

.. code-block:: bash

   maple policy act POLICY_ID --image PATH --instruction TEXT [OPTIONS]

Arguments
^^^^^^^^^

``POLICY_ID``
    ID of running policy

Options
^^^^^^^

``--image, -i PATH`` (required)
    Path to image file

``--instruction TEXT`` (required)
    Language instruction

``--unnorm-key, -u TEXT``
    Dataset key for action unnormalization

``--port INTEGER``
    Daemon port

Example
^^^^^^^

.. code-block:: bash

   maple policy act openvla-7b-abc123 \
       --image observation.png \
       --instruction "pick up the red block"

Output:

.. code-block:: text

   Action: [0.012, -0.034, 0.156, 0.001, 0.002, 0.003, 1.0]

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
