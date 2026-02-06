======
config
======

Configuration management commands.

Synopsis
========

.. code-block:: bash

   maple config show
   maple config init [OPTIONS]
   maple config path

Subcommands
===========

show
----

Display current configuration (merged from all sources).

.. code-block:: bash

   maple config show

Example
^^^^^^^

.. code-block:: bash

   maple config show

Output:

.. code-block:: yaml

   logging:
     level: INFO
     file: null
     verbose: false
   containers:
     memory_limit: 32g
     shm_size: 2g
     startup_timeout: 300
     health_check_interval: 30
   policy:
     default_device: cuda:0
     model_kwargs: {}
     model_load_kwargs: {}
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

init
----

Create default config file.

.. code-block:: bash

   maple config init [OPTIONS]

Notes
^^^^^
- Please restart the CLI Daemon to load the new config properly.

Options
^^^^^^^

``--force, -f``
    Overwrite existing config file

Example
^^^^^^^

.. code-block:: bash

   # Create config (won't overwrite existing)
   maple config init

   # Force overwrite
   maple config init --force

Output:

.. code-block:: text

   ✓ Config created: /home/user/.maple/config.yaml

path
----

Show config file path.

.. code-block:: bash

   maple config path

Example
^^^^^^^

.. code-block:: bash

   maple config path

Output:

.. code-block:: text

   /home/user/.maple/config.yaml

See Also
========

- :doc:`../guides/configuration` — Configuration guide
