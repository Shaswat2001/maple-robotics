====
eval
====

Run batch evaluation across multiple tasks and seeds.

Synopsis
========

.. code-block:: bash

   maple eval POLICY_ID ENV_ID [OPTIONS]

Description
===========

The ``eval`` command runs comprehensive batch evaluations, automatically iterating 
over tasks and seeds. Results are saved as JSON, with optional Markdown and CSV exports.

Arguments
=========

``POLICY_ID``
    ID of a running policy (e.g., ``openvla-7b-a1b2c3d4``)

``ENV_ID``
    ID of a running environment (e.g., ``libero-x1y2z3w4``)

Options
=======

``--tasks, -t TEXT`` (required)
    Tasks to evaluate. Can be:
    
    - Suite name: ``libero_10`` (fetches all tasks in suite)
    - Explicit list: ``libero_10/0,libero_10/1,libero_10/2``
    - Single task: ``libero_10/0``

``--seeds, -s TEXT``
    Random seeds (comma-separated). Default: ``0``

``--max-steps, -m INTEGER``
    Maximum steps per episode. Default: from config (300)

``--unnorm-key, -u TEXT``
    Dataset key for action unnormalization (policy-specific)

``--save-video, -v``
    Save rollout videos

``--video-dir TEXT``
    Directory for videos. Default: ``~/.maple/videos``

``--output, -o PATH``
    Output directory for results. Default: ``~/.maple/results``

``--format, -f TEXT``
    Output format: ``json``, ``markdown``, ``csv``, ``all``. Default: ``json``

``--parallel, -p INTEGER``
    Number of parallel evaluations (experimental). Default: 1

``--port INTEGER``
    Daemon port to connect to

Examples
========

Basic Evaluation
----------------

.. code-block:: bash

   # Evaluate on full suite
   maple eval openvla-7b-abc libero-xyz --tasks libero_10 --seeds 0,1,2

   # Evaluate specific tasks
   maple eval openvla-7b-abc libero-xyz \
       --tasks libero_10/0,libero_10/1 \
       --seeds 0,1,2,3,4

With Video Recording
--------------------

.. code-block:: bash

   maple eval openvla-7b-abc libero-xyz \
       --tasks libero_10 \
       --seeds 0 \
       --save-video \
       --video-dir ./videos

Custom Output
-------------

.. code-block:: bash

   maple eval openvla-7b-abc libero-xyz \
       --tasks libero_10 \
       --seeds 0,1,2 \
       --output ./results \
       --format all  # JSON + Markdown + CSV

Extended Evaluation
-------------------

.. code-block:: bash

   maple eval openvla-7b-abc libero-xyz \
       --tasks libero_10 \
       --seeds 0,1,2,3,4,5,6,7,8,9 \
       --max-steps 500

Output
======

Console Output
--------------

.. code-block:: text

   Batch Evaluation
     Policy: openvla-7b-abc123
     Environment: libero-xyz789
     Tasks: 10
     Seeds: [0, 1, 2]
     Total episodes: 30
     Max steps: 300

   [1/30] ✓ libero_10/0 seed=0 reward=1.000
   [2/30] ✓ libero_10/0 seed=1 reward=1.000
   [3/30] ✗ libero_10/0 seed=2 reward=0.234
   ...

   Batch Evaluation Results: batch-20240131-123456
   ==================================================
   Policy: openvla-7b-abc123
   Environment: libero-xyz789
   Tasks: 10 | Seeds: 3

   Overall Results:
     Episodes: 30
     Success Rate: 72.0%
     Avg Reward: 0.847
     Avg Steps: 156.3
     Avg Duration: 12.34s

   Per-Task Results:
     libero_10/0: 100.0% (3/3) reward=1.000
     libero_10/1: 66.7% (2/3) reward=0.756
     libero_10/2: 100.0% (3/3) reward=1.000
     ...

   ✓ Results saved: results/batch-20240131-123456.json

JSON Output Structure
---------------------

.. code-block:: json

   {
     "batch_id": "batch-20240131-123456",
     "policy_id": "openvla-7b-abc123",
     "env_id": "libero-xyz789",
     "tasks": ["libero_10/0", "libero_10/1", ...],
     "seeds": [0, 1, 2],
     "max_steps": 300,
     "started_at": 1706745600.0,
     "finished_at": 1706746200.0,
     "total_episodes": 30,
     "successful_episodes": 22,
     "success_rate": 0.733,
     "avg_reward": 0.847,
     "avg_steps": 156.3,
     "task_stats": {
       "libero_10/0": {
         "total": 3,
         "successful": 3,
         "success_rate": 1.0,
         "avg_reward": 1.0
       },
       ...
     },
     "results": [
       {
         "run_id": "eval-abc123",
         "task": "libero_10/0",
         "seed": 0,
         "success": true,
         "steps": 156,
         "total_reward": 1.0,
         "duration_seconds": 12.34
       },
       ...
     ]
   }

See Also
========

- :doc:`../guides/quickstart` — Basic evaluation walkthrough
- ``maple report`` — Generate reports from saved results
