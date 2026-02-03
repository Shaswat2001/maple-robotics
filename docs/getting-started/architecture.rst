Architecture
============

Understanding MAPLE's architecture helps you extend it and debug issues.

Overview
--------

MAPLE uses a **daemon-based architecture** where a central server orchestrates Docker containers running policies and environments.

.. code-block:: text

   ┌─────────────────────────────────────────────────────────────┐
   │                        MAPLE CLI                             │
   │                           ↓                                  │
   │                    MAPLE Daemon (:8080)                      │
   │         ┌───────────────┼───────────────┐                   │
   │         ↓               ↓               ↓                    │
   │   Policy Manager   Env Manager    Scheduler                 │
   │         ↓               ↓               ↓                    │
   │   Policy           Env            Adapter                    │
   │   Containers       Containers     Registry                  │
   └─────────────────────────────────────────────────────────────┘

Core Components
---------------

1. MAPLE Daemon
~~~~~~~~~~~~~~~

**Location:** ``maple/server/daemon.py``

The daemon is a FastAPI server that:

- Manages lifecycle of Docker containers
- Tracks state of policies and environments
- Coordinates rollouts between policies and environments
- Exposes REST API for CLI and external tools

**Key responsibilities:**

- Container orchestration
- State persistence (``~/.maple/state.json``)
- Health checking
- Resource cleanup

2. CLI
~~~~~~

**Location:** ``maple/cmd/cli.py``

The command-line interface built with Typer:

- Sends HTTP requests to the daemon
- Provides user-friendly commands
- Handles formatting and display

**Design philosophy:**

- CLI is thin - all logic in daemon
- Commands map 1:1 to API endpoints
- Rich output for better UX

3. Policy Backend
~~~~~~~~~~~~~~~~~

**Location:** ``maple/backend/policy/``

Each policy type has:

- **Base class** (``base.py``) - Interface definition
- **Implementation** (e.g., ``openvla.py``) - Specific policy
- **Registry** (``registry.py``) - Policy discovery

**Policy Container:**

.. code-block:: python

   # Inside Docker container
   class PolicyServer:
       def load(self, checkpoint_path):
           """Load model weights"""
           
       def act(self, observation, instruction):
           """Generate action from observation"""

4. Environment Backend
~~~~~~~~~~~~~~~~~~~~~~

**Location:** ``maple/backend/envs/``

Similar structure to policies:

- **Base class** - Standard environment interface
- **Implementation** - Specific environment (LIBERO, etc.)
- **Registry** - Environment discovery

**Environment Container:**

.. code-block:: python

   # Inside Docker container
   class EnvServer:
       def setup(self, task_name):
           """Initialize task"""
           
       def reset(self):
           """Reset environment"""
           
       def step(self, action):
           """Execute action, return observation"""

5. Adapter System
~~~~~~~~~~~~~~~~~

**Location:** ``maple/adapters/``

Adapters bridge policies and environments by handling:

- **Observation transformation** - Convert env obs → policy input
- **Action transformation** - Convert policy output → env action
- **Task-specific logic** - Language instructions, etc.

.. code-block:: python

   class Adapter:
       def adapt_observation(self, obs, task_info):
           """Transform environment obs for policy"""
           
       def adapt_action(self, action):
           """Transform policy action for environment"""

**Why adapters?**

- Different policies expect different input formats
- Different environments provide different observations
- Decouple policy and environment implementations

6. Scheduler
~~~~~~~~~~~~

**Location:** ``maple/scheduler/scheduler.py``

Coordinates rollouts:

1. Get observation from environment
2. Get action from policy (via adapter)
3. Step environment with action
4. Collect metrics
5. Save videos if requested

Data Flow
---------

Here's what happens during a rollout:

.. code-block:: text

   CLI → Daemon → Scheduler
                     ↓
             ┌───────┴────────┐
             ↓                ↓
          Adapter          Adapter
             ↓                ↓
          Policy            Env
             ↓                ↓
          Action        Observation
             └────────┬───────┘
                      ↓
                   Metrics

File System Layout
------------------

.. code-block:: text

   ~/.maple/
   ├── state.json              # Daemon state
   │   ├── policies: {}        # Active policies
   │   ├── environments: {}    # Active environments
   │   └── pulled: {}          # Downloaded components
   ├── daemon.pid              # Daemon process ID
   ├── models/                 # Model weights
   │   └── openvla/
   │       └── 7b/
   │           ├── config.json
   │           └── model.safetensors
   └── videos/                 # Evaluation videos
       └── run-12345678.mp4

Communication
-------------

All components communicate via HTTP:

.. list-table::
   :header-rows: 1

   * - Component
     - Protocol
     - Port
   * - Daemon
     - HTTP
     - 8080 (default)
   * - Policy Container
     - HTTP
     - Random (55000+)
   * - Env Container
     - HTTP
     - Random (55000+)

**Why HTTP?**

- Language agnostic
- Easy debugging (curl, browsers)
- Simple container networking
- Standard error handling

Extension Points
----------------

Adding a New Policy
~~~~~~~~~~~~~~~~~~~

1. Create ``maple/backend/policy/mypolicy.py``:

.. code-block:: python

   from .base import PolicyBackend

   class MyPolicyBackend(PolicyBackend):
       def load(self, checkpoint_path):
           # Load your model
           pass
           
       def act(self, observation, instruction):
           # Generate action
           pass

2. Register in ``maple/backend/policy/registry.py``
3. Create Docker image with policy server

Adding a New Environment
~~~~~~~~~~~~~~~~~~~~~~~~~

1. Create ``maple/backend/envs/myenv.py``:

.. code-block:: python

   from .base import EnvBackend

   class MyEnvBackend(EnvBackend):
       def setup(self, task_name):
           # Initialize environment
           pass

2. Register in ``maple/backend/envs/registry.py``
3. Create Docker image with env server

Adding a New Adapter
~~~~~~~~~~~~~~~~~~~~

1. Create ``maple/adapters/mypolicy_myenv.py``:

.. code-block:: python

   from .base import Adapter

   class MyPolicyMyEnvAdapter(Adapter):
       def adapt_observation(self, obs, task_info):
           # Transform observation
           pass

2. Register in ``maple/adapters/registry.py``

Design Principles
-----------------

1. **Separation of Concerns** - CLI, daemon, policies, envs are independent
2. **Extensibility** - Registry pattern for adding new components
3. **Isolation** - Docker containers prevent dependency conflicts
4. **Efficiency** - Share weights via volume mounts, no duplication
5. **Simplicity** - HTTP for everything, standard REST patterns

Performance Considerations
--------------------------

- **Model Loading:** Weights loaded once per serve, cached in GPU memory
- **Container Reuse:** Containers persist until explicitly stopped
- **Batching:** Policies support batch inference for multiple environments
- **Volume Mounts:** Weights mounted read-only, no copying

Next Steps
----------

- :doc:`../advanced/adapters` - Custom Adapters Guide
- :doc:`../advanced/docker` - Docker Images
- :doc:`../api/server` - API Reference
