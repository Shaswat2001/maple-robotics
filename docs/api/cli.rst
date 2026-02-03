CLI Reference
=============

The MAPLE command-line interface provides an intuitive way to interact with the daemon.

.. currentmodule:: maple.cmd.cli

Main Commands
-------------

.. autofunction:: main

Daemon Management
-----------------

.. autofunction:: serve
.. autofunction:: status
.. autofunction:: stop

Policy Management
-----------------

.. autofunction:: pull_policy
.. autofunction:: serve_policy
.. autofunction:: list_policies
.. autofunction:: policy_info
.. autofunction:: policy_stop

Environment Management
----------------------

.. autofunction:: pull_env
.. autofunction:: serve_env
.. autofunction:: list_envs
.. autofunction:: env_info
.. autofunction:: env_stop
.. autofunction:: env_tasks

Evaluation
----------

.. autofunction:: run

Command Examples
----------------

Daemon Commands
~~~~~~~~~~~~~~~

Start daemon in foreground:

.. code-block:: bash

   maple serve

Start daemon in background:

.. code-block:: bash

   maple serve --detach

Custom port:

.. code-block:: bash

   maple serve --port 8081

Check status:

.. code-block:: bash

   maple status

Stop daemon:

.. code-block:: bash

   maple stop

Policy Commands
~~~~~~~~~~~~~~~

Pull policy weights:

.. code-block:: bash

   maple pull policy openvla:7b

Serve policy:

.. code-block:: bash

   maple serve policy openvla:7b --device cuda:0
   maple serve policy openvla:7b --attn flash_attention_2
   maple serve policy openvla:7b --attn sdpa

List running policies:

.. code-block:: bash

   maple list policy

Get policy info:

.. code-block:: bash

   maple policy info openvla-7b-abc123

Stop policy:

.. code-block:: bash

   maple policy stop openvla-7b-abc123

Environment Commands
~~~~~~~~~~~~~~~~~~~~

Pull environment:

.. code-block:: bash

   maple pull env libero

Serve environment:

.. code-block:: bash

   maple serve env libero
   maple serve env libero --num-envs 4
   maple serve env libero --host-port 8001

List running environments:

.. code-block:: bash

   maple list env

Get environment info:

.. code-block:: bash

   maple env info libero-xyz789

List available tasks:

.. code-block:: bash

   maple env tasks libero

Stop environment:

.. code-block:: bash

   maple env stop libero-xyz789

Evaluation Commands
~~~~~~~~~~~~~~~~~~~

Run evaluation:

.. code-block:: bash

   maple run <policy_id> <env_id> --task libero_10/0

With options:

.. code-block:: bash

   maple run <policy_id> <env_id> \
       --task libero_10/0 \
       --max-steps 500 \
       --seed 42 \
       --save-video \
       --instruction "pick up the red block"
