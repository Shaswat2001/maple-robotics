===
env
===

Environment-related operations.

Synopsis
========

.. code-block:: bash

   maple env setup ENV_ID --task TASK [OPTIONS]
   maple env reset ENV_ID [OPTIONS]
   maple env step ENV_ID --action VALUES [OPTIONS]
   maple env stop ENV_ID [OPTIONS]

Subcommands
===========

setup
-----

Setup environment with a specific task.

.. code-block:: bash

   maple env setup ENV_ID --task TASK [OPTIONS]

Arguments
^^^^^^^^^

``ENV_ID``
    ID of running environment

Options
^^^^^^^

``--task, -t TEXT`` (required)
    Task specification (e.g., ``libero_10/0``)

``--seed, -s INTEGER``
    Random seed

``--port INTEGER``
    Daemon port

Example
^^^^^^^

.. code-block:: bash

   maple env setup libero-xyz --task libero_10/0 --seed 42

Output:

.. code-block:: text

   ✓ Environment setup
     Task: LIVING_ROOM_SCENE_pick_up_the_black_bowl_...
     Instruction: Pick up the black bowl and place it on the plate.

reset
-----

Reset the environment to initial state.

.. code-block:: bash

   maple env reset ENV_ID [OPTIONS]

Arguments
^^^^^^^^^

``ENV_ID``
    ID of running environment

Options
^^^^^^^

``--seed, -s INTEGER``
    Random seed for reset

``--port INTEGER``
    Daemon port

Example
^^^^^^^

.. code-block:: bash

   maple env reset libero-xyz --seed 42

Output:

.. code-block:: text

   ✓ Environment reset
     Observation keys: ['agentview_image', 'robot0_eye_in_hand_image', ...]

step
----

Take a step in the environment.

.. code-block:: bash

   maple env step ENV_ID --action VALUES [OPTIONS]

Arguments
^^^^^^^^^

``ENV_ID``
    ID of running environment

Options
^^^^^^^

``--action, -a FLOAT`` (required, multiple)
    Action values (specify multiple times)

``--port INTEGER``
    Daemon port

Example
^^^^^^^

.. code-block:: bash

   maple env step libero-xyz \
       -a 0.01 -a -0.02 -a 0.05 -a 0.0 -a 0.0 -a 0.0 -a 1.0

Output:

.. code-block:: text

   Step result:
     Reward: 0.0000
     Terminated: False
     Truncated: False
     Success: False

stop
----

Stop an environment container.

.. code-block:: bash

   maple env stop ENV_ID [OPTIONS]

Arguments
^^^^^^^^^

``ENV_ID``
    ID of environment to stop

Options
^^^^^^^

``--port INTEGER``
    Daemon port

Example
^^^^^^^

.. code-block:: bash

   maple env stop libero-xyz

Output:

.. code-block:: text

   ✓ Stopped: libero-xyz
