=====
serve
=====

Start the Maple daemon or serve policies/environments.

Synopsis
========

.. code-block:: bash

   maple serve [OPTIONS]
   maple serve policy NAME [OPTIONS]
   maple serve env NAME [OPTIONS]

Description
===========

The ``serve`` command has three modes:

1. **Daemon mode**: Start the background daemon
2. **Policy mode**: Load a policy into a container
3. **Env mode**: Start an environment container

Daemon Mode
===========

Start the Maple daemon:

.. code-block:: bash

   maple serve [OPTIONS]

Options
-------

``--port INTEGER``
    Port to run daemon on (default: from config, typically 8000)

``--device TEXT``
    Default GPU device (default: from config, typically cpu)

``--detach, -d``
    Run daemon in background

Examples
--------

.. code-block:: bash

   # Start daemon in foreground
   maple serve

   # Start on specific port
   maple serve --port 9000

   # Run in background
   maple serve --detach

   # Use specific GPU
   maple serve --device cuda:1

Policy Mode
===========

Load a policy into a Docker container:

.. code-block:: bash

   maple serve policy NAME [OPTIONS]

Arguments
---------

``NAME``
    Policy specification (e.g., ``openvla:7b``, ``smolvla:libero``)

Options
-------

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)

``--device, -d TEXT``
    GPU device for this policy (default: from config, typically cpu)

``--host-port, -p INTEGER``
    Bind container to specific host port

``--mdl-kwargs, -a STR``
    Model-specific loading parameters

Examples
--------

.. code-block:: bash

   # Serve default variant
   maple serve policy openvla

   # Serve specific variant
   maple serve policy openvla:7b

   # Use Flash Attention
   maple serve policy openvla:7b --mdl-kwargs '{"attention_implementation" : "flash_attention_2"}'

   # Bind to specific port
   maple serve policy openvla:7b --host-port 8080

   # Use different GPU
   maple serve policy openvla:7b --device cuda:1

Output
------

.. code-block:: text

   ✓ Serving policy: openvla:7b
     Policy ID: openvla-7b-a1b2c3d4
     Port: http://localhost:50123
     Device: cuda:0
     Parameters :
        attention_implementation: sdpa

Environment Mode
================

Start environment container(s):

.. code-block:: bash

   maple serve env NAME [OPTIONS]

Arguments
---------

``NAME``
    Environment name (e.g., ``libero``, ``simplerenv``)

Options
-------

``--port INTEGER``
    Daemon port to connect to

``--num-envs, -n INTEGER``
    Number of parallel environment instances

``--host-port, -p INTEGER``
    Bind container to specific host port (only with num_envs=1)

Examples
--------

.. code-block:: bash

   # Start single environment
   maple serve env libero

   # Start multiple parallel environments
   maple serve env libero --num-envs 4

   # Bind to specific port
   maple serve env libero --host-port 8081

Output
------

.. code-block:: text

   ✓ Serving env: libero (1 instance(s))
     • libero-x1y2z3w4 → http://localhost:50124

Notes
=====

- The daemon must be running before serving policies or environments
- Policy IDs and Environment IDs are generated automatically
- Use ``maple status`` to see all running policies and environments
- Use ``maple policy stop`` or ``maple env stop`` to stop containers
