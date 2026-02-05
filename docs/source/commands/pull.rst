====
pull
====

Download policy weights or environment Docker images.

Synopsis
========

.. code-block:: bash

   maple pull policy NAME [OPTIONS]
   maple pull env NAME [OPTIONS]

Pull Policy
===========

Download policy weights from Hugging Face:

.. code-block:: bash

   maple pull policy NAME [OPTIONS]

Arguments
---------

``NAME``
    Policy specification (e.g., ``openvla:7b``, ``smolvla:libero``)

Options
-------

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)

Examples
--------

.. code-block:: bash

   # Pull default variant
   maple pull policy openvla

   # Pull specific variant
   maple pull policy openvla:7b

   # Pull SmolVLA
   maple pull policy smolvla:libero

Notes
-----

- Weights are stored in ``~/.maple/weights/``
- Download progress is shown in the daemon logs
- Subsequent pulls use cached weights

Pull Environment
================

Pull environment Docker image:

.. code-block:: bash

   maple pull env NAME [OPTIONS]

Arguments
---------

``NAME``
    Environment name (e.g., ``libero``, ``simplerenv``)

Options
-------

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)

Examples
--------

.. code-block:: bash

   # Pull LIBERO
   maple pull env libero

   # Pull SimplerEnv
   maple pull env simplerenv

Notes
-----

- Requires Docker to be installed and running
- Images are pulled from Docker Hub or built locally
- Build images manually with: ``docker build -t maplerobotics/libero:latest docker/libero/``
