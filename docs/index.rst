MAPLE Documentation
===================

**MAPLE** (Model And Policy Learning Evaluation) is a modern framework for orchestrating and evaluating robotics policies in simulation environments.

.. image:: https://img.shields.io/pypi/v/maple-robotics.svg
   :target: https://pypi.org/project/maple-robotics/
   :alt: PyPI version

.. image:: https://img.shields.io/badge/License-MIT-blue.svg
   :target: https://opensource.org/licenses/MIT
   :alt: License

.. image:: https://img.shields.io/badge/python-3.8+-blue.svg
   :target: https://www.python.org/downloads/
   :alt: Python version

Overview
--------

MAPLE is a daemon-based orchestration tool for running Vision-Language-Action (VLA) models and robotics simulation environments. It provides a clean CLI and REST API for managing containerized policies and environments.

Key Features
------------

🚀 **Daemon Architecture**
   Background service orchestrates everything

🐳 **Docker-Based**
   Isolated containers for policies and environments

🔌 **Extensible**
   Plugin system for custom policies and environments

📊 **Evaluation Ready**
   Built-in rollout system with video saving

⚡ **Efficient**
   Share model weights across runs, no duplication

🎯 **Simple CLI**
   Intuitive commands for all operations

Quick Example
-------------

.. code-block:: bash

   # Start the daemon
   maple serve

   # Pull and serve components
   maple pull policy openvla:7b
   maple serve policy openvla:7b --device cuda:0

   maple pull env libero
   maple serve env libero

   # Run evaluation
   maple run <policy_id> <env_id> --task libero_10/0 --save-video

Architecture
------------

.. code-block:: text

   ┌─────────────────────────────────────────────────────────────────────┐
   │                           MAPLE CLI                                 │
   ├─────────────────────────────────────────────────────────────────────┤
   │                      MAPLE Daemon (:8080)                           │
   │  - Orchestrates policies and environments                           │
   │  - Manages rollouts and evaluation                                  │
   │  - Tracks state and handles                                         │
   ├────────────────────────────┬────────────────────────────────────────┤
   │     Policy Containers      │         Env Containers                 │
   │  ┌──────────────────────┐  │  ┌──────────────────────┐              │
   │  │ OpenVLA              │  │  │ LIBERO               │              │
   │  │ - Load models        │  │  │ - Setup tasks        │              │
   │  │ - Generate actions   │  │  │ - Step simulation    │              │
   │  │ - Batched inference  │  │  │ - Return observations│              │
   │  └──────────────────────┘  │  └──────────────────────┘              │
   └────────────────────────────┴────────────────────────────────────────┘

Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   getting-started/installation
   getting-started/quickstart
   getting-started/architecture

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   guide/daemon
   guide/policies
   guide/environments
   guide/evaluations

.. toctree::
   :maxdepth: 2
   :caption: Advanced Topics

   advanced/docker
   advanced/adapters
   advanced/configuration

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/cli
   api/server
   api/scheduler
   api/backend
   api/adapters

.. toctree::
   :maxdepth: 2
   :caption: Examples

   examples/basic
   examples/custom-policy
   examples/custom-env

.. toctree::
   :maxdepth: 1
   :caption: Development

   contributing
   changelog

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
