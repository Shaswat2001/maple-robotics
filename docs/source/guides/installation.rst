============
Installation
============

Requirements
============

- Python 3.10+
- Docker (images are pulled automatically from Docker Hub)
- **(Optional but recommended)** NVIDIA GPU with CUDA 12.1+ for faster policy inference

   - CPU-only mode is supported but will be significantly slower
   - NVIDIA Container Toolkit required only if using GPU acceleration

Install from PyPI
=================

.. code-block:: bash

   pip install maple-robotics

Install from Source
===================

.. code-block:: bash

   git clone https://github.com/Shaswat2001/maple-robotics.git
   cd maple-robotics
   pip install -e .

Optional Dependencies
=====================

For development:

.. code-block:: bash

    pip install maple-robotics[dev]

For documentation:

.. code-block:: bash

   pip install maple-robotics[docs]

Docker Setup
============

Maple uses Docker to run policies and environments in isolated containers. 
**Docker images are automatically pulled from Docker Hub** when you first use a policy or environment.

1. Install Docker
-----------------

Follow the official Docker installation guide for your OS:
https://docs.docker.com/get-docker/

GPU Acceleration (Optional)
============================

For significantly faster policy inference, GPU acceleration is recommended.

.. note::
   
   CPU-only inference is supported but can be 10-100x slower depending on the policy.
   Only install GPU support if you have an NVIDIA GPU.

2. Install NVIDIA Container Toolkit
------------------------------------

**Only required if you want GPU acceleration.**

For GPU support with NVIDIA GPUs:

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
    #   Device: cuda:0  (or cpu if no GPU)

Docker Image Management
=======================

Policy and environment Docker images are **automatically pulled from Docker Hub** when needed.

.. code-block:: bash

    # Images are pulled automatically on first use
    # For example, when you first run:
    maple pull openvla:latest  # Pulls maple/openvla:latest from Docker Hub

Available Pre-built Images
---------------------------

The following images are available on Docker Hub:

- ``maple/openvla:latest`` - OpenVLA policy
- ``maple/smolvla:latest`` - SmolVLA policy  
- ``maple/libero:latest`` - LIBERO environment

You can also pull images manually:

.. code-block:: bash

    docker pull maple/openvla:latest
    docker pull maple/smolvla:latest
    docker pull maple/libero:latest

Building Custom Images (Advanced)
==================================

**Only needed if you want to modify the Docker images.**

If you need to customize the policy or environment containers, you can build images locally:

.. code-block:: bash

    # Build OpenVLA policy image
    docker build -t maple/openvla:latest docker/openvla/
    
    # Build SmolVLA policy image  
    docker build -t maple/smolvla:latest docker/smolvla/
    
    # Build LIBERO environment image
    docker build -t maple/libero:latest docker/libero/

Troubleshooting
===============

Docker Permission Issues
------------------------

If you get permission errors when running Docker commands:

.. code-block:: bash

    # Add your user to the docker group
    sudo usermod -aG docker $USER
    
    # Log out and log back in for changes to take effect

Disk Space
----------

Docker images can be large (several GB). Ensure you have sufficient disk space:

.. code-block:: bash

    # Check Docker disk usage
    docker system df
    
    # Clean up unused images
    docker system prune -a

CPU vs GPU Performance
----------------------

Expected inference times (approximate):

- **GPU (NVIDIA RTX 3090)**: 10-50ms per inference
- **CPU (Intel i9)**: 500-2000ms per inference

For interactive control or real-time applications, GPU acceleration is strongly recommended.