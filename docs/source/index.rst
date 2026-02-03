.. Maple documentation master file

======================================
Maple - Robotics Policy Evaluation CLI
======================================

.. image:: assets/MAPLE.svg
   :alt: Maple Logo
   :align: center
   :width: 300px

.. raw:: html

   <p align="center">
   <strong>A unified CLI daemon for evaluating robotics policies across diverse simulation environments</strong>
   </p>

   <p align="center">
   <a href="https://github.com/Shaswat2001/maple-robotics.git"><img src="https://img.shields.io/badge/GitHub-maple-blue?logo=github" alt="GitHub"></a>
   <a href="https://pypi.org/project/maple-robotics/"><img src="https://img.shields.io/pypi/v/maple-robotics" alt="PyPI"></a>
   <a href="https://maple-robotics.readthedocs.io"><img src="https://readthedocs.org/projects/maple-robotics/badge/?version=latest" alt="Documentation"></a>
   <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
   </p>

----

Why Maple?
==========

**The Problem**

Evaluating robotics policies—whether Vision-Language-Action (VLA) models, imitation learning policies, 
or reinforcement learning agents—across different simulation environments is painful:

- **Environment chaos**: Every simulator has its own observation format, action space, and API quirks
- **Dependency hell**: MuJoCo, PyBullet, Isaac Gym, LIBERO—each with conflicting dependencies
- **Integration tax**: Each policy-environment combination requires custom glue code
- **No standardization**: Comparing policies across environments means rewriting evaluation scripts

**The Solution**

Maple provides a **daemon-based architecture** that:

1. **Containerizes everything** — Policies and environments run in isolated Docker containers
2. **Standardizes the interface** — One CLI to rule them all
3. **Handles the translation** — Adapters automatically convert between policy outputs and environment inputs
4. **Scales evaluation** — Batch evaluation across tasks, seeds, and configurations

.. code-block:: bash

   # Start the daemon
   maple serve

   # Pull and serve a policy
   maple pull policy openvla:7b
   maple serve policy openvla:7b

   # Pull and serve an environment  
   maple pull env libero
   maple serve env libero

   # Run evaluation
   maple eval openvla-7b-xxx libero-yyy --tasks libero_10 --seeds 0,1,2

**That's it.** No dependency conflicts. No custom scripts. Just results.

----

Demo
====

.. raw:: html

   <p align="center">
   <em>Demo video coming soon</em>
   </p>

   <!-- Uncomment when video is ready
   <p align="center">
   <video width="100%" controls>
   <source src="_static/demo.mp4" type="video/mp4">
   Your browser does not support the video tag.
   </video>
   </p>
   -->

----

Key Features
============

🐳 **Docker-First Architecture**
   Every policy and environment runs in its own container. No more dependency conflicts.

🔌 **Adapter System**
   Automatic translation between policy outputs and environment inputs. 
   Write once, evaluate everywhere.

📊 **Batch Evaluation**
   Run evaluations across multiple tasks, seeds, and configurations with a single command.
   Get aggregated metrics and per-task breakdowns.

⚙️ **Flexible Configuration**
   YAML config files, environment variables, or CLI flags—use what works for you.

🏥 **Health Monitoring**
   Background health checks keep your containers running. Auto-restart on failure.

💾 **Persistent State**
   SQLite-backed state storage. Resume evaluations, track history, query results.

----

Architecture
============

.. code-block:: text

   ┌─────────────────────────────────────────────────────────────┐
   │                        maple CLI                            │
   └─────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                     Maple Daemon                            │
   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
   │  │ Policy      │  │ Environment │  │ Adapter             │  │
   │  │ Backends    │  │ Backends    │  │ Registry            │  │
   │  │             │  │             │  │                     │  │
   │  │ • OpenVLA   │  │ • LIBERO    │  │ • openvla:libero    │  │
   │  │ • SmolVLA   │  │ • SimplerEnv│  │ • smolvla:libero    │  │
   │  │ • ...       │  │ • ...       │  │ • ...               │  │
   │  └──────┬──────┘  └──────┬──────┘  └─────────────────────┘  │
   └─────────┼────────────────┼──────────────────────────────────┘
             │                │
             ▼                ▼
   ┌─────────────────┐  ┌─────────────────┐
   │ Policy Container │  │ Env Container   │
   │ (Docker + GPU)   │  │ (Docker + X11)  │
   │                  │  │                 │
   │ HTTP: /act       │  │ HTTP: /step     │
   │       /load      │  │       /reset    │
   │       /health    │  │       /setup    │
   └─────────────────┘  └─────────────────┘

----

Supported Policies
==================

+------------+---------------------------+------------------+
| Policy     | Variants                  | Status           |
+============+===========================+==================+
| OpenVLA    | 7B                        | ✅ Supported     |
+------------+---------------------------+------------------+
| SmolVLA    | libero, base              | ✅ Supported     |
+------------+---------------------------+------------------+
| Octo       | base, small               | 🚧 Coming Soon   |
+------------+---------------------------+------------------+
| RT-1/RT-2  | -                         | 📋 Planned       |
+------------+---------------------------+------------------+

Supported Environments
======================

+-------------+---------------------------+------------------+
| Environment | Task Suites               | Status           |
+=============+===========================+==================+
| LIBERO      | libero_10, libero_90, ... | ✅ Supported     |
+-------------+---------------------------+------------------+
| SimplerEnv  | google_robot, widowx      | 🚧 Coming Soon   |
+-------------+---------------------------+------------------+
| RoboCasa    | -                         | 📋 Planned       |
+-------------+---------------------------+------------------+
| ManiSkill   | -                         | 📋 Planned       |
+-------------+---------------------------+------------------+

----

Quick Links
===========

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api
----