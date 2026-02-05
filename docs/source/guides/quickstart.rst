==========
Quickstart
==========

This guide walks you through evaluating your first policy with Maple.

Step 1: Start the Daemon
========================

Maple uses a daemon process to manage policies and environments:

.. code-block:: bash

   maple serve

The daemon starts on port 8000 by default. You can change this:

.. code-block:: bash

   maple serve --port 9000 --device cuda:1

To run in the background:

.. code-block:: bash

   maple serve --detach

Step 2: Pull a Policy
=====================

Download policy weights from Hugging Face and pull docker image:

.. code-block:: bash

   maple pull policy openvla:latest

This downloads the OpenVLA 7B model to ``~/.maple/models/``.

Step 3: Serve the Policy
========================

Load the policy into a Docker container:

.. code-block:: bash

   maple serve policy openvla:latest

Output:

.. code-block:: text

   ✓ Serving policy: openvla:latest
     Policy ID: openvla-latest-a1b2c3d4
     Port: http://localhost:50123
     Device: cuda:0

Note the **Policy ID** — you'll need it for evaluation.

Step 4: Pull an Environment
===========================

Pull the environment Docker image:

.. code-block:: bash

   maple pull env libero

Step 5: Serve the Environment
=============================

Start an environment container:

.. code-block:: bash

   maple serve env libero

Output:

.. code-block:: text

   ✓ Serving env: libero (1 instance(s))
     • libero-x1y2z3w4 → http://localhost:50124

Step 6: Run a Single Evaluation
===============================

Run the policy on a single task:

.. code-block:: bash

   maple run openvla-7b-a1b2c3d4 libero-x1y2z3w4 \
       --task libero_10/0 \
       --max-steps 300

Output:

.. code-block:: text

   ✓ Task completed successfully!
   
   Results:
     Run ID: run-abc123
     Steps: 156
     Total Reward: 1.0000
     Terminated: True

Step 7: Batch Evaluation
========================

Evaluate across multiple tasks and seeds:

.. code-block:: bash

   maple eval openvla-7b-a1b2c3d4 libero-x1y2z3w4 libero \
       --tasks libero_10 \
       --seeds 0,1,2 \
       --output results/

Output:

.. code-block:: text

   Batch Evaluation Results: batch-20240131-123456
   ==================================================
   Policy: openvla-7b-a1b2c3d4
   Environment: libero-x1y2z3w4
   Tasks: 10 | Seeds: 3
   
   Overall Results:
     Episodes: 30
     Success Rate: 72.0%
     Avg Reward: 0.847
     Avg Steps: 156.3

   Per-Task Results:
     libero_10/0: 100.0% (3/3) reward=1.000
     libero_10/1: 66.7% (2/3) reward=0.756
     ...

   ✓ Results saved: results/batch-20240131-123456.json

Step 8: Check Status
====================

View running policies and environments:

.. code-block:: bash

   maple status

Output:

.. code-block:: text

   VLA daemon running
     Port: 8000
     Device: cuda:0
   
   Pulled: 1 policies, 1 envs
   
   Serving:
     Policies:
       • openvla-7b-a1b2c3d4
     Environments:
       • libero-x1y2z3w4

Step 9: Cleanup Resources
=========================

Remove a policy when no longer needed:

.. code-block:: bash

   maple remove policy openvla 7b

This stops containers, removes database entries, and deletes model weights.

Remove an environment:

.. code-block:: bash

   maple remove env libero

If you manually deleted files, sync the database:

.. code-block:: bash

   # After manual deletion: rm -rf ~/.maple/models/openvla/
   maple sync policies

Step 10: Stop Everything
========================

Stop a specific policy:

.. code-block:: bash

   maple policy stop openvla-7b-a1b2c3d4

Stop the daemon (cleans up all containers):

.. code-block:: bash

   maple stop

Next Steps
==========

- :doc:`configuration` — Customize defaults with config files
- :doc:`../commands/eval` — Advanced evaluation options
- :doc:`../commands/remove` — Clean resource management
- :doc:`../commands/sync` — Database synchronization
- :doc:`adding-policies` — Add support for new policies

