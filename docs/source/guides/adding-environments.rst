====================
Adding Environments
====================

This guide explains how to add support for a new simulation environment to Maple.

Overview
========

Adding a new environment requires:

1. Creating a Docker image with the environment server
2. Implementing an environment backend class
3. Creating adapters for each supported policy

Step 1: Create Docker Image
===========================

Create ``docker/myenv/env_server.py`` with FastAPI endpoints:

- ``GET /health`` - Health check
- ``POST /setup`` - Setup task
- ``POST /reset`` - Reset environment
- ``POST /step`` - Take action step
- ``GET /tasks`` - List available tasks

Step 2: Create Backend Class
============================

Create ``maple/backend/envs/myenv.py``:

.. code-block:: python

   from maple.backend.envs.base import DockerEnvBackend
   
   class MyEnvBackend(DockerEnvBackend):
       name = "myenv"
       IMAGE = "maple/myenv:latest"
       CONTAINER_PORT = 8000

Register in ``maple/backend/envs/registry.py``.

Step 3: Create Adapters
=======================

Create adapters for each policy you want to support with this environment.

See :doc:`../api/adapters` for detailed documentation.
