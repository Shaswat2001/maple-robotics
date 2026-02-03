=============
Configuration
=============

Maple uses a hierarchical configuration system with the following priority (highest to lowest):

1. CLI arguments
2. Environment variables
3. Config file (``~/.maple/config.yaml``)
4. Built-in defaults

Config File
===========

Create a default config file:

.. code-block:: bash

   maple config init

This creates ``~/.maple/config.yaml``:

.. code-block:: yaml

   # Maple Configuration

   logging:
     level: INFO           # DEBUG, INFO, WARNING, ERROR
     file: null            # Optional log file path
     verbose: false

   containers:
     memory_limit: 32g     # Container memory limit
     shm_size: 2g          # Shared memory size
     startup_timeout: 300  # Seconds to wait for container startup
     health_check_interval: 30

   policy:
     default_device: cuda:0
     attn_implementation: sdpa  # flash_attention_2, sdpa, eager

   env:
     default_num_envs: 1

   daemon:
     host: 0.0.0.0
     port: 8000

   eval:
     max_steps: 300
     save_video: false
     video_dir: ~/.maple/videos
     results_dir: ~/.maple/results

View Current Config
-------------------

.. code-block:: bash

   maple config show

Get Config Path
---------------

.. code-block:: bash

   maple config path
   # Output: /home/user/.maple/config.yaml

Environment Variables
=====================

Override any config value with environment variables:

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Variable
     - Config Key
     - Example
   * - ``MAPLE_DEVICE``
     - ``policy.default_device``
     - ``cuda:1``
   * - ``MAPLE_ATTN``
     - ``policy.attn_implementation``
     - ``flash_attention_2``
   * - ``MAPLE_LOG_LEVEL``
     - ``logging.level``
     - ``DEBUG``
   * - ``MAPLE_LOG_FILE``
     - ``logging.file``
     - ``/var/log/maple.log``
   * - ``MAPLE_MEMORY_LIMIT``
     - ``containers.memory_limit``
     - ``64g``
   * - ``MAPLE_STARTUP_TIMEOUT``
     - ``containers.startup_timeout``
     - ``600``
   * - ``MAPLE_DAEMON_PORT``
     - ``daemon.port``
     - ``9000``
   * - ``MAPLE_MAX_STEPS``
     - ``eval.max_steps``
     - ``500``
   * - ``MAPLE_SAVE_VIDEO``
     - ``eval.save_video``
     - ``true``

Example:

.. code-block:: bash

   MAPLE_DEVICE=cuda:1 MAPLE_LOG_LEVEL=DEBUG maple serve

CLI Arguments
=============

CLI arguments always override config and environment variables:

.. code-block:: bash

   # These override everything
   maple serve --port 9000 --device cuda:2
   maple eval ... --max-steps 500 --save-video

Common Configuration Patterns
=============================

Multi-GPU Setup
---------------

Config file for a multi-GPU machine:

.. code-block:: yaml

   policy:
     default_device: cuda:0

   # Run different policies on different GPUs
   # Use CLI override: maple serve policy model --device cuda:1

High Memory Models
------------------

For large models (30B+):

.. code-block:: yaml

   containers:
     memory_limit: 64g
     shm_size: 4g
     startup_timeout: 600  # More time for large models

Debugging
---------

Verbose logging:

.. code-block:: yaml

   logging:
     level: DEBUG
     file: ~/.maple/logs/maple.log
     verbose: true

Production Evaluation
---------------------

For batch evaluation runs:

.. code-block:: yaml

   eval:
     max_steps: 500
     save_video: true
     video_dir: /data/eval_videos
     results_dir: /data/eval_results

   containers:
     health_check_interval: 60  # Less frequent checks

Per-Project Configuration
=========================

You can specify a custom config file:

.. code-block:: bash

   maple --config ./project_config.yaml serve

This is useful for project-specific settings without modifying your global config.
