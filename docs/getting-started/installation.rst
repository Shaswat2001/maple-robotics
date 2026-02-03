Installation
============

Prerequisites
-------------

Before installing MAPLE, ensure you have:

- **Python 3.8+** installed
- **Docker** installed and running
- **CUDA-capable GPU** (optional, for GPU acceleration)

Install from PyPI
-----------------

.. code-block:: bash

   pip install maple-robotics

Install from Source
-------------------

For the latest development version:

.. code-block:: bash

   git clone https://github.com/yourusername/maple.git
   cd maple
   pip install -e .

Docker Images
-------------

MAPLE uses Docker containers for policies and environments. You'll need to build the images:

Build Policy Images
~~~~~~~~~~~~~~~~~~~

OpenVLA (without flash attention):

.. code-block:: bash

   docker build -t maple/openvla:latest docker/openvla/

OpenVLA (with flash attention for faster inference):

.. code-block:: bash

   docker build -t maple/openvla:flash \
       --build-arg INSTALL_FLASH_ATTN=true \
       docker/openvla/

Build Environment Images
~~~~~~~~~~~~~~~~~~~~~~~~~

LIBERO environment:

.. code-block:: bash

   docker build -t maple/libero:latest docker/libero/

Verify Installation
-------------------

Check that MAPLE is installed correctly:

.. code-block:: bash

   maple --version

Start the daemon to verify everything works:

.. code-block:: bash

   maple serve

You should see:

.. code-block:: text

   🍁 MAPLE daemon starting on port 8080...
   ✓ Daemon ready!

GPU Support
-----------

To use GPU acceleration with policies:

1. Install `NVIDIA Container Toolkit <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html>`_

2. Verify GPU access in Docker:

   .. code-block:: bash

      docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

Configuration
-------------

MAPLE stores data in ``~/.maple/``:

.. code-block:: text

   ~/.maple/
   ├── state.json       # Current state
   ├── daemon.pid       # Daemon process ID
   ├── models/          # Downloaded model weights
   └── videos/          # Saved evaluation videos

No additional configuration needed for basic usage!

Next Steps
----------

- :doc:`quickstart` - Run your first evaluation
- :doc:`architecture` - Understand how MAPLE works
