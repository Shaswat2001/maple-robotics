Server API Reference
====================

The MAPLE daemon exposes a REST API for programmatic access.

.. currentmodule:: maple.server.daemon

Daemon Server
-------------

.. autoclass:: DaemonServer
   :members:
   :undoc-members:
   :show-inheritance:

REST API Endpoints
------------------

The daemon exposes the following HTTP endpoints:

Status
~~~~~~

.. http:get:: /status

   Get daemon status and version information.

   **Example response:**

   .. code-block:: json

      {
        "status": "running",
        "version": "0.0.1",
        "uptime": 3600
      }

Policy Management
~~~~~~~~~~~~~~~~~

.. http:post:: /policy/pull

   Download policy weights from HuggingFace.

   **Request body:**

   .. code-block:: json

      {
        "policy_name": "openvla:7b"
      }

.. http:post:: /policy/serve

   Start a policy container.

   **Request body:**

   .. code-block:: json

      {
        "policy_name": "openvla:7b",
        "device": "cuda:0",
        "attn": "sdpa"
      }

.. http:get:: /policy/info/(string:policy_id)

   Get information about a running policy.

   :param policy_id: The policy ID

.. http:post:: /policy/stop/(string:policy_id)

   Stop a running policy.

   :param policy_id: The policy ID

.. http:post:: /policy/act

   Get action from policy.

   **Request body:**

   .. code-block:: json

      {
        "policy_id": "openvla-7b-abc123",
        "observation": [...],
        "instruction": "pick up the block"
      }

Environment Management
~~~~~~~~~~~~~~~~~~~~~~

.. http:post:: /env/pull

   Pull environment Docker image.

   **Request body:**

   .. code-block:: json

      {
        "env_name": "libero"
      }

.. http:post:: /env/serve

   Start an environment container.

   **Request body:**

   .. code-block:: json

      {
        "env_name": "libero",
        "num_envs": 1
      }

.. http:get:: /env/info/(string:env_id)

   Get information about a running environment.

   :param env_id: The environment ID

.. http:post:: /env/stop/(string:env_id)

   Stop a running environment.

   :param env_id: The environment ID

.. http:post:: /env/setup

   Setup a task in the environment.

   **Request body:**

   .. code-block:: json

      {
        "env_id": "libero-xyz789",
        "task_name": "libero_10/0"
      }

.. http:post:: /env/reset

   Reset the environment.

   **Request body:**

   .. code-block:: json

      {
        "env_id": "libero-xyz789"
      }

.. http:post:: /env/step

   Step the environment with an action.

   **Request body:**

   .. code-block:: json

      {
        "env_id": "libero-xyz789",
        "action": [0.1, 0.2, 0.3, ...]
      }

Evaluation
~~~~~~~~~~

.. http:post:: /run

   Run a policy evaluation.

   **Request body:**

   .. code-block:: json

      {
        "policy_id": "openvla-7b-abc123",
        "env_id": "libero-xyz789",
        "task": "libero_10/0",
        "max_steps": 300,
        "save_video": true
      }

   **Response:**

   .. code-block:: json

      {
        "run_id": "run-12345678",
        "steps": 156,
        "total_reward": 1.0,
        "success": true,
        "video_path": "~/.maple/videos/run-12345678.mp4"
      }

Python API Usage
----------------

You can also interact with the daemon programmatically:

.. code-block:: python

   import requests

   # Get daemon status
   response = requests.get("http://localhost:8080/status")
   print(response.json())

   # Start policy
   response = requests.post(
       "http://localhost:8080/policy/serve",
       json={"policy_name": "openvla:7b", "device": "cuda:0"}
   )
   policy_id = response.json()["policy_id"]

   # Run evaluation
   response = requests.post(
       "http://localhost:8080/run",
       json={
           "policy_id": policy_id,
           "env_id": env_id,
           "task": "libero_10/0"
       }
   )
   results = response.json()

Error Handling
--------------

All API endpoints return standard HTTP status codes:

- **200 OK** - Request successful
- **400 Bad Request** - Invalid parameters
- **404 Not Found** - Resource not found
- **500 Internal Server Error** - Server error

Error responses include a message:

.. code-block:: json

   {
     "error": "Policy not found",
     "detail": "No policy with ID openvla-7b-abc123"
   }
