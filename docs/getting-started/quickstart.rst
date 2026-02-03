Quick Start
===========

This guide walks you through your first MAPLE evaluation in 5 minutes.

Step 1: Start the Daemon
-------------------------

The daemon orchestrates all policies and environments:

.. code-block:: bash

   maple serve

.. tip::
   Use ``maple serve --detach`` to run in the background.

Step 2: Pull Components
------------------------

Download a policy and environment:

.. code-block:: bash

   # Pull OpenVLA 7B model weights
   maple pull policy openvla:7b

   # Pull LIBERO environment
   maple pull env libero

.. note::
   Weights are downloaded once to ``~/.maple/models/`` and reused across runs.

Step 3: Serve Components
-------------------------

Start the policy and environment containers:

.. code-block:: bash

   # Serve policy on GPU 0
   maple serve policy openvla:7b --device cuda:0

   # Serve environment
   maple serve env libero

You'll get IDs like:

.. code-block:: text

   Policy ID: openvla-7b-abc123
   Env ID: libero-xyz789

Step 4: Run Evaluation
-----------------------

Run the policy on a task:

.. code-block:: bash

   maple run openvla-7b-abc123 libero-xyz789 \
       --task libero_10/0 \
       --max-steps 300 \
       --save-video

Output:

.. code-block:: text

   🍁 Running evaluation...
   Step 156/300 | Reward: 1.0000
   ✓ Task completed successfully!

   Results:
     Run ID: run-12345678
     Steps: 156
     Total Reward: 1.0000
     Success: True
     Video: ~/.maple/videos/run-12345678.mp4

Step 5: Cleanup
---------------

When done, stop components:

.. code-block:: bash

   maple policy stop openvla-7b-abc123
   maple env stop libero-xyz789
   maple stop  # Stop daemon

Complete Example
----------------

Here's the full workflow in one script:

.. code-block:: bash

   #!/bin/bash

   # Start daemon
   maple serve --detach

   # Setup
   maple pull policy openvla:7b
   maple pull env libero

   # Serve components
   POLICY_ID=$(maple serve policy openvla:7b --device cuda:0 | grep "Policy ID:" | cut -d: -f2 | xargs)
   ENV_ID=$(maple serve env libero | grep "Env ID:" | cut -d: -f2 | xargs)

   # Run evaluation
   maple run $POLICY_ID $ENV_ID \
       --task libero_10/0 \
       --max-steps 300 \
       --save-video

   # Cleanup
   maple policy stop $POLICY_ID
   maple env stop $ENV_ID
   maple stop

What's Next?
------------

- :doc:`../guide/policies` - Learn about policy management
- :doc:`../guide/environments` - Work with different environments
- :doc:`../advanced/adapters` - Create custom policy-environment pairs

Common Tasks
------------

List Available Tasks
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   maple env tasks libero

Check Status
~~~~~~~~~~~~

.. code-block:: bash

   maple status               # Daemon status
   maple list policy          # Running policies
   maple list env             # Running environments

Get Policy Info
~~~~~~~~~~~~~~~

.. code-block:: bash

   maple policy info openvla-7b-abc123

Multiple Evaluations
~~~~~~~~~~~~~~~~~~~~

Run the same policy on multiple tasks:

.. code-block:: bash

   for task in libero_10/{0..9}; do
       maple run $POLICY_ID $ENV_ID --task $task --save-video
   done

Troubleshooting
---------------

Port Already in Use
~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   maple serve --port 8081

GPU Not Available
~~~~~~~~~~~~~~~~~

Check Docker GPU access:

.. code-block:: bash

   docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

Container Won't Start
~~~~~~~~~~~~~~~~~~~~~

Check logs:

.. code-block:: bash

   docker logs <container_id>

Get container ID from:

.. code-block:: bash

   maple list policy  # or maple list env
