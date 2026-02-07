===
run
===

Run a single policy evaluation on a specific task.

Synopsis
========

.. code-block:: bash

   maple run POLICY_ID ENV_ID [OPTIONS]

Description
===========

The ``run`` command executes a single episode of a policy on a specified environment 
task. It displays real-time progress and results including success status, steps taken, 
rewards, and video paths.

Arguments
=========

``POLICY_ID``
    ID of a running policy (e.g., ``openvla-7b-a1b2c3d4``)

``ENV_ID``
    ID of a running environment (e.g., ``libero-x1y2z3w4``)

Options
=======

``--task, -t TEXT`` (required)
    Task specification (e.g., ``libero_10/0``)

``--instruction, -i TEXT``
    Override the default task instruction

``--max-steps, -m INTEGER``
    Maximum steps per episode. Default: from config (300)

``--seed, -s INTEGER``
    Random seed for reproducibility

``--unnorm-key, -u TEXT``
    Dataset key for action unnormalization (policy-specific)

``--save-video, -v``
    Save rollout video

``--model-kwargs, -u STR``
    Model-specific parameters

``--env-kwargs, -e STR``
    Env-specific parameters

``--video-path TEXT``
    Custom video output path. Default: ``~/.maple/videos``

``--timeout INTEGER``
    Constant multiplied with max_steps to determine the timeout

``--port INTEGER``
    aemon port to connect to (default: from config, typically 8000)

Examples
========

Basic Run
---------

.. code-block:: bash

   # Run policy on a specific task
   maple run openvla-7b-abc libero-xyz --task libero_10/0

With Seed
---------

.. code-block:: bash

   # Run with specific seed for reproducibility
   maple run openvla-7b-abc libero-xyz \
       --task libero_10/0 \
       --seed 42

With Video Recording
--------------------

.. code-block:: bash

   # Save video of the rollout
   maple run openvla-7b-abc libero-xyz \
       --task libero_10/0 \
       --save-video \
       --video-path ./my-videos

Custom Instruction
------------------

.. code-block:: bash

   # Override task instruction
   maple run openvla-7b-abc libero-xyz \
       --task libero_10/0 \
       --instruction "pick up the red block and place it in the basket"

Extended Episode
----------------

.. code-block:: bash

   # Run with more steps
   maple run openvla-7b-abc libero-xyz \
       --task libero_10/0 \
       --max-steps 500

Output
======

Console Output
--------------

.. code-block:: text

   Running policy on task...
     Policy: openvla-7b-abc123
     Env: libero-xyz789
     Task: libero_10/0
     Max steps: 300

   ✓ Task completed successfully!

   Results:
     Run ID: eval-abc123def456
     Steps: 156
     Total Reward: 1.0000
     Terminated: True
     Truncated: False
     Video saved: ~/.maple/videos/eval-abc123def456.mp4

Notes
=====

- The timeout for the HTTP request is calculated as ``max_steps × timeout`` to 
  allow for long episodes
- If a request times out, increase the ``--timeout`` multiplier or reduce ``--max-steps``
- Video files are saved with the run ID as the filename

See Also
========

- :doc:`eval` — Batch evaluation across multiple tasks and seeds
- :doc:`../guides/quickstart` — Basic usage walkthrough