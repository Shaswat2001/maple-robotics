============
Installation
============

Requirements
============

- Python 3.10+
- Docker with GPU support (NVIDIA Container Toolkit)
- NVIDIA GPU with CUDA 12.1+ (for policy inference)

Install from PyPI
=================

.. code-block:: bash

   pip install maple-robotics

Install from Source
===================

.. code-block:: bash

   git clone https://github.com/arenaxlabs/maple.git
   cd maple
   pip install -e ".[dev]"

Optional Dependencies
=====================

For rotation utilities (euler ↔ axis-angle conversions):

.. code-block:: bash

   pip install maple-robotics[rotation]

For development:

.. code-block:: bash

   pip install maple-robotics[dev]

For documentation:

.. code-block:: bash

   pip install maple-robotics[docs]

Docker Setup
============

Maple uses Docker to run policies and environments in isolated containers.

1. Install Docker
-----------------

Follow the official Docker installation guide for your OS:
https://docs.docker.com/get-docker/

2. Install NVIDIA Container Toolkit
-----------------------------------

For GPU support (required for most policies):

.. code-block:: bash

   # Add the package repositories
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
       sudo tee /etc/apt/sources.list.d/nvidia-docker.list

   # Install nvidia-docker2
   sudo apt-get update
   sudo apt-get install -y nvidia-docker2
   sudo systemctl restart docker

3. Verify GPU Access
--------------------

.. code-block:: bash

   docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi

You should see your GPU information.

Build Policy/Environment Images
===============================

Maple provides Dockerfiles for supported policies and environments:

.. code-block:: bash

   # Build OpenVLA policy image
   docker build -t maple/openvla:latest docker/openvla/

   # Build SmolVLA policy image  
   docker build -t maple/smolvla:latest docker/smolvla/

   # Build LIBERO environment image
   docker build -t maple/libero:latest docker/libero/

Verify Installation
===================

.. code-block:: bash

   # Check CLI is available
   maple --help

   # Start daemon and check status
   maple serve &
   maple status

   # You should see:
   # VLA daemon running
   #   Port: 8000
   #   Device: cuda:0
