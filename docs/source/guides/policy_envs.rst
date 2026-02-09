====================================
Policies & Environments Reference
====================================

This page provides detailed information about all available policies and environments, including their configuration parameters (kwargs) for both model loading and inference.

----

Policies
========

OpenVLA
-------

**Description**

OpenVLA (Open Vision-Language-Action) is a 7B parameter transformer-based vision-language-action model for robotic manipulation. It takes visual observations and natural language instructions as input and outputs robot actions.

**Available Versions**

- ``7b`` - OpenVLA 7B parameter model (``openvla/openvla-7b``)
- ``latest`` - Alias for the 7B model (default)

**Container Image**

``maplerobotics/openvla:latest``

**Inputs**

- ``image`` - Visual observation (RGB image)
- ``instruction`` - Natural language task instruction

**Outputs**

- ``action`` - Predicted robot action vector (unnormalized to target space)

**Model Load Parameters** (``model_load_kwargs``)

OpenVLA uses standard model loading and does not require additional kwargs for loading.

**Inference Parameters** (``model_kwargs``)

+----------------+----------+----------+--------------------------------------------------+
| Parameter      | Type     | Required | Description                                      |
+================+==========+==========+==================================================+
| ``unnorm_key`` | ``str``  | **YES**  | Dataset name for action unnormalization.         |
|                |          |          | Must be provided for executable actions.         |
|                |          |          |                                                  |
|                |          |          | **Valid values:**                                |
|                |          |          |                                                  |
|                |          |          | - ``bridge_orig``                             |
|                |          |          | - ``libero_object``                              |
|                |          |          | - ``libero_goal``                                |
|                |          |          | - ``libero_10``                                  |
|                |          |          | - ``bridge``                                     |
|                |          |          | - ``fractal``                                    |
+----------------+----------+----------+--------------------------------------------------+

**Important Notes**

- **unnorm_key is REQUIRED**: OpenVLA outputs normalized actions that must be converted using dataset-specific statistics. Without unnormalization, the actions cannot be executed.
- The unnorm_key must match the environment/dataset you're evaluating on (e.g., use ``bridge_orig``).

----

SmolVLA
-------

**Description**

SmolVLA (Small Vision-Language-Action) is a compact vision-language-action model for robotic manipulation. It supports multi-modal observations including images and proprioceptive state, and directly outputs actions in the target space without requiring unnormalization.

**Available Versions**

- ``libero`` - SmolVLA fine-tuned for LIBERO benchmark (``HuggingFaceVLA/smolvla_libero``)
- ``base`` - Base SmolVLA trained on diverse datasets (``lerobot/smolvla_base``)

**Container Image**

``maplerobotics/smolvla:latest``

**Inputs**

- ``image`` - Visual observation (RGB image, can include multiple camera views)
- ``state`` - Proprioceptive robot state (joint positions, velocities, etc.)
- ``instruction`` - Natural language task instruction

**Outputs**

- ``action`` - Predicted robot action vector in target action space

**Model Load Parameters** (``model_load_kwargs``)

SmolVLA uses standard model loading and does not require additional kwargs for loading.

**Inference Parameters** (``model_kwargs``)

SmolVLA does not require any additional inference parameters. All observations are passed through the adapter, and the model directly outputs actions in the target space.

**Important Notes**

- SmolVLA handles multi-modal observations automatically through the adapter system.
- The ``libero`` version is specifically fine-tuned for LIBERO tasks and may perform better than ``base`` on those benchmarks.
- Unlike OpenVLA, SmolVLA does not require action unnormalization.

----

OpenPI
------

**Description**

OpenPI (π₀ / π₀.₅) is Physical Intelligence's family of vision-language-action models for robotic manipulation. Available in multiple sizes and task-specific variants, OpenPI supports multi-modal observations and is trained on diverse real-world robot datasets.

**Available Versions**

Base models (for fine-tuning):

- ``pi0_base`` - π₀ base model
- ``pi0_fast_base`` - π₀ fast variant base model
- ``pi05_base`` - π₀.₅ base model

DROID fine-tuned (mobile manipulation):

- ``pi0_fast_droid``
- ``pi0_droid``
- ``pi05_droid``

ALOHA fine-tuned (bimanual manipulation):

- ``pi0_aloha_towel``
- ``pi0_aloha_tupperware``
- ``pi0_aloha_pen_uncap``

LIBERO fine-tuned (long-horizon manipulation):

- ``pi05_libero``

Bridge and Fractal Dataset fine-tuned (long-horizon manipulation):

- ``HaomingSong/openpi0-bridge-lora``
- ``"HaomingSong/openpi0-fractal-lora``

Aliases:

- ``latest`` - Alias for ``pi05_droid`` (default)

**Container Image**

``maplerobotics/openpi:latest``

**Model Source**

Models are downloaded from Google Cloud Storage (``gs://openpi-assets``) using anonymous access (no credentials required).

**Inputs**

- ``image`` - Visual observation (supports multiple camera views)
- ``state`` - Proprioceptive robot state
- ``prompt`` - Natural language instruction

**Outputs**

- ``action`` - Predicted robot action vector in target action space

**Model Load Parameters** (``model_load_kwargs``)

+------------------+----------+----------+--------------------------------------------------+
| Parameter        | Type     | Required | Description                                      |
+==================+==========+==========+==================================================+
| ``config_name``  | ``str``  | NO       | OpenPI model configuration identifier.           |
|                  |          |          | Auto-inferred from version if not provided.      |
|                  |          |          |                                                  |
|                  |          |          | **Values:** Same as version names                |
|                  |          |          | (e.g., ``pi05_droid``, ``pi0_base``)             |
+------------------+----------+----------+--------------------------------------------------+

**Inference Parameters** (``model_kwargs``)

OpenPI does not require any additional inference parameters. All observations are passed through the adapter.

**Important Notes**

- The ``config_name`` parameter is automatically inferred from the version, so manual specification is typically not needed.
- OpenPI models are downloaded from a public S3 bucket and require ``fsspec[gs]`` and ``gsfs`` to be installed.
- Different variants are optimized for different robot platforms (DROID for mobile manipulation, ALOHA for bimanual tasks, etc.).

----

Environments
============

LIBERO
------

**Description**

LIBERO (Language-Instructed Benchmarks for Embodied Robot Learning) is a suite of robotic manipulation tasks with natural language instructions. It uses MuJoCo for physics simulation with OSMesa for headless rendering.

**Container Image**

``maplerobotics/libero:latest``

**Task Suites**

+------------------+------+------------------------------------------------+
| Suite            | Tasks| Description                                    |
+==================+======+================================================+
| ``libero_spatial`` | 10 | Spatial reasoning tasks                        |
+------------------+------+------------------------------------------------+
| ``libero_object``  | 10 | Object manipulation tasks                      |
+------------------+------+------------------------------------------------+
| ``libero_goal``    | 10 | Goal-conditioned tasks                         |
+------------------+------+------------------------------------------------+
| ``libero_10``      | 10 | Diverse benchmark tasks                        |
+------------------+------+------------------------------------------------+
| ``libero_90``      | 90 | Large-scale diverse task suite                 |
+------------------+------+------------------------------------------------+

**Environment Setup Parameters** (``env_kwargs``)

LIBERO environments are configured through task selection and do not require additional kwargs for standard usage.

**Container Configuration**

- **Rendering**: OSMesa (headless, software rendering)
- **GPU**: Not required (CPU-only)
- **Memory Limit**: 4GB
- **Environment Variables**: ``MUJOCO_GL=osmesa``

**Important Notes**

- LIBERO uses OSMesa for rendering, so no GPU or X11 display is required.
- Task instructions are automatically loaded when setting up a task.
- Use ``maple env list-tasks libero`` to see all available tasks.

----

RoboCasa
--------

**Description**

RoboCasa is a large-scale simulation framework for training robots to perform everyday tasks in kitchen environments. It provides both atomic (single-step) and composite (multi-step) manipulation tasks.

**Container Image**

``maplerobotics/robocasa:latest``

**Task Categories**

+---------------+------+------------------------------------------------------------+
| Category      | Tasks| Description                                                |
+===============+======+============================================================+
| ``atomic``    | 25   | Low-level primitive operations that cannot be              |
|               |      | decomposed further                                         |
+---------------+------+------------------------------------------------------------+
| ``composite`` | 97   | High-level multi-step behaviors composed of                |
|               |      | atomic actions in structured sequences                     |
+---------------+------+------------------------------------------------------------+

**Environment Setup Parameters** (``env_kwargs``)

+------------------+----------+----------+--------------------------------------------------+
| Parameter        | Type     | Required | Description                                      |
+==================+==========+==========+==================================================+
| ``robot``        | ``str``  | NO       | Robocasa can add any desired robot in an env.    |
|                  |          |          | PandaOmron is selected if not provided.          |
|                  |          |          |                                                  |
|                  |          |          | **Values:** Same as version names                |
|                  |          |          | (e.g., ``PandaOmron``, ``GR1``)                  |
+------------------+----------+----------+--------------------------------------------------+
| ``layout_id``    | ``int``  | NO       | Layout ID defining variation in the env.         |
|                  |          |          |                                                  |
+------------------+----------+----------+--------------------------------------------------+
| ``style_id``     | ``int``  | NO       | Style ID defining variation in the env.          |
+------------------+----------+----------+--------------------------------------------------+
**Container Configuration**

- **Rendering**: OSMesa (headless, software rendering)
- **GPU**: Not required (CPU-only)
- **Memory Limit**: 4GB
- **Environment Variables**: ``MUJOCO_GL=osmesa``

**Important Notes**

- RoboCasa uses OSMesa for rendering, so no GPU or X11 display is required.
- Composite tasks involve multi-step reasoning and are more challenging than atomic tasks.
- Use ``maple env list-tasks robocasa`` to see all available tasks with instructions.

----

AlohaSim
--------

**Description**

AlohaSim is a simulation environment suite for the ALOHA (A Low-cost Open-source Hardware System for Bimanual Teleoperation) robot. It provides a collection of bimanual manipulation tasks for robot learning and evaluation with MuJoCo physics simulation.

**Container Image**

``maplerobotics/alohasim:latest``

**Task Suites**

+------------------+------+------------------------------------------------------------+
| Suite            | Tasks| Description                                                |
+==================+======+============================================================+
| ``basic``        | 5    | Basic bimanual manipulation tasks                          |
+------------------+------+------------------------------------------------------------+
| ``instruction``  | 12   | Language-conditioned instruction following tasks           |
+------------------+------+------------------------------------------------------------+
| ``dexterous``    | 3    | Complex dexterous manipulation tasks                       |
+------------------+------+------------------------------------------------------------+

**Environment Setup Parameters** (``env_kwargs``)

AlohaSim environments are configured through task selection and do not require additional kwargs for standard usage.

**Container Configuration**

- **Rendering**: EGL (headless rendering with hardware acceleration)
- **GPU**: Recommended for EGL rendering
- **Memory Limit**: 4GB
- **Environment Variables**: 
  
  - ``MUJOCO_GL=egl``
  - ``PYOPENGL_PLATFORM=egl``

**Usage Example**

.. code-block:: python

   # Start an AlohaSim environment
   maple serve env alohasim
   
   # Run evaluation on basic tasks
   maple eval policy-id env-id \
       --tasks basic \
       --seeds 0,1,2

**Important Notes**

- AlohaSim is designed for bimanual manipulation with the ALOHA robot platform.
- The environment uses EGL for rendering, which can leverage GPU acceleration when available.
- Tasks range from basic pick-and-place to complex dexterous manipulation requiring coordinated bimanual control.
- Use ``maple env list-tasks alohasim`` to see all available tasks with instructions.

----

SimplerEnv
----------

**Description**

SimplerEnv combines Bridge and Fractal simulation environments, providing tasks for both WidowX and Google Robot platforms with natural language instructions.

**Container Image**

``maplerobotics/simplerenv:latest``

**Task Suites**

+--------------+------+------------------------------------------------+
| Suite        | Tasks| Description                                    |
+==============+======+================================================+
| ``bridge``   | 4    | Tasks with the WidowX robot                    |
+--------------+------+------------------------------------------------+
| ``fractal``  | 16   | Tasks with the Google Robot                    |
+--------------+------+------------------------------------------------+

**Environment Setup Parameters** (``env_kwargs``)

SimplerEnv environments are configured through task selection and do not require additional kwargs for standard usage.

**Container Configuration**

- **Rendering**: EGL (headless rendering with hardware acceleration)
- **GPU**: Recommended for EGL rendering
- **Memory Limit**: 4GB
- **Environment Variables**: 
  
  - ``MUJOCO_GL=egl``
  - ``PYOPENGL_PLATFORM=egl``
  - ``SAPIEN_DISABLE_VULKAN_RAY_TRACING=1``
  - ``SAPIEN_DISABLE_VULKAN_RAY_QUERY=1``

**Important Notes**

- SimplerEnv uses EGL for rendering, which can leverage GPU acceleration when available.
- Bridge tasks use the WidowX robot platform, while Fractal tasks use the Google Robot.
- Use ``maple env list-tasks simplerenv`` to see all available tasks.

----

Common Patterns
===============

Policy-Environment Compatibility
---------------------------------

+------------------+-------------------+-------------------------------------+
| Policy           | Environment       | Required kwargs                     |
+==================+===================+=====================================+
| OpenVLA          | LIBERO            | ``unnorm_key="libero_spatial"``     |
|                  |                   | (or other LIBERO suite)             |
+------------------+-------------------+-------------------------------------+
| OpenVLA          | SimplerEnv        | ``unnorm_key="bridge"`` or          |
|                  |                   | ``unnorm_key="fractal"``            |
+------------------+-------------------+-------------------------------------+
| SmolVLA (libero) | LIBERO            | No kwargs needed                    |
+------------------+-------------------+-------------------------------------+
| SmolVLA (base)   | Multiple          | No kwargs needed                    |
+------------------+-------------------+-------------------------------------+
| OpenPI (libero)  | LIBERO            | No kwargs needed                    |
+------------------+-------------------+-------------------------------------+
| OpenPI (droid)   | Multiple          | No kwargs needed                    |
+------------------+-------------------+-------------------------------------+

Passing Model Kwargs
---------------------

Model kwargs can be passed in two ways:

**Via Command Line**

.. code-block:: bash

   # During evaluation
   maple eval policy-id env-id \
       --tasks task_suite \
       --model-kwargs '{"unnorm_key": "libero_spatial"}'
   
   # During single run
   maple run policy-id env-id task_name \
       --model-kwargs '{"unnorm_key": "libero_spatial"}'

**Via Configuration File**

.. code-block:: yaml

   # config.yaml
   evaluation:
     model_kwargs:
       unnorm_key: "libero_spatial"

Environment Kwargs
------------------

Environment kwargs can be passed similarly:

.. code-block:: bash

   # During environment setup
   maple run policy-id env-id task_name \
       --env-kwargs '{}'

Currently, the supported environments (LIBERO, SimplerEnv) do not require environment kwargs for standard usage. Future environment backends may expose additional configuration options.

----

Adding Custom Parameters
=========================

When developing custom policies or environments, you can extend the kwargs system:

**For Policies**

Implement the ``act()`` method to accept and use ``model_kwargs``:

.. code-block:: python

   def act(
       self,
       handle: PolicyHandle,
       payload: Any,
       instruction: str,
       model_kwargs: Optional[Dict[str, Any]] = {}
   ) -> List[float]:
       # Extract custom kwargs
       temperature = model_kwargs.get("temperature", 1.0)
       top_p = model_kwargs.get("top_p", 0.9)
       
       # Use in inference
       ...

**For Environments**

Implement the ``setup()`` method to accept and use ``env_kwargs``:

.. code-block:: python

   def setup(
       self,
       handle: EnvHandle,
       task: str,
       seed: Optional[int] = None,
       env_kwargs: Optional[Dict[str, Any]] = {}
   ) -> Dict:
       # Extract custom kwargs
       render_mode = env_kwargs.get("render_mode", "rgb_array")
       camera_id = env_kwargs.get("camera_id", 0)
       
       # Use in setup
       ...

See the :doc:`/guides/adding-policies` and :doc:`/guides/adding-environments` guides for more details.