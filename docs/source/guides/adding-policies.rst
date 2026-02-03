===============
Adding Policies
===============

This guide explains how to add support for a new policy to Maple.

Overview
========

Adding a new policy requires:

1. Creating a Docker image with the policy server
2. Implementing a policy backend class
3. Creating an adapter for each environment

Step 1: Create Docker Image
===========================

Create a new directory under ``docker/``:

.. code-block:: bash

   mkdir -p docker/mypolicy

Create ``docker/mypolicy/policy_server.py`` with FastAPI endpoints:

- ``GET /health`` - Health check
- ``POST /load`` - Load model weights
- ``POST /act`` - Get action for observation
- ``GET /info`` - Model information

Create ``docker/mypolicy/Dockerfile`` based on the OpenVLA example.

Step 2: Create Backend Class
============================

Create ``maple/backend/policy/mypolicy.py``:

.. code-block:: python

   from maple.backend.policy.base import DockerPolicyBackend
   
   class MyPolicyBackend(DockerPolicyBackend):
       name = "mypolicy"
       IMAGE = "maple/mypolicy:latest"
       HF_REPOS = {
           "base": "org/mypolicy-base",
           "large": "org/mypolicy-large",
       }
       DEFAULT_VERSION = "base"

Register in ``maple/backend/policy/registry.py``:

.. code-block:: python

   from maple.backend.policy.mypolicy import MyPolicyBackend
   
   POLICY_BACKENDS = {
       "mypolicy": MyPolicyBackend,
       # ...
   }

Step 3: Create Adapter
======================

Create ``maple/adapters/mypolicy_libero.py`` implementing observation and action transformations.

Register in ``maple/adapters/registry.py``.

See :doc:`../api/adapters` for detailed adapter documentation.
