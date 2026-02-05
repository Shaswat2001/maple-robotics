===
env
===

Environment-related operations.

Synopsis
========

.. code-block:: bash

   maple env setup ENV_ID --task TASK [OPTIONS]
   maple env reset ENV_ID [OPTIONS]
   maple env step ENV_ID --action VALUES [OPTIONS]
   maple env stop ENV_ID [OPTIONS]

Subcommands
===========

setup
-----

Setup environment with a specific task.

.. code-block:: bash

   maple env setup ENV_ID --task TASK [OPTIONS]

Arguments
^^^^^^^^^

``ENV_ID``
    ID of running environment

Options
^^^^^^^

``--task, -t TEXT`` (required)
    Task specification (e.g., ``libero_10/0``)

``--seed, -s INTEGER``
    Random seed

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)

Example
^^^^^^^

.. code-block:: bash

   maple env setup libero-xyz --task libero_10/0 --seed 42

Output:

.. code-block:: text

   ✓ Environment setup
     Task: LIVING_ROOM_SCENE_pick_up_the_black_bowl_...
     Instruction: Pick up the black bowl and place it on the plate.

reset
-----

Reset the environment to initial state.

.. code-block:: bash

   maple env reset ENV_ID [OPTIONS]

Arguments
^^^^^^^^^

``ENV_ID``
    ID of running environment

Options
^^^^^^^

``--seed, -s INTEGER``
    Random seed for reset

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)    

Example
^^^^^^^

.. code-block:: bash

   maple env reset libero-xyz --seed 42

Output:

.. code-block:: text

   ✓ Environment reset
     Observation keys: ['agentview_image', 'robot0_eye_in_hand_image', ...]

step
----

Take a step in the environment.

.. code-block:: bash

   maple env step ENV_ID --action VALUES [OPTIONS]

Arguments
^^^^^^^^^

``ENV_ID``
    ID of running environment

Options
^^^^^^^

``--action, -a LIST[FLOAT]`` (required)
    Action values (specify list of values)

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)

Example
^^^^^^^

.. code-block:: bash

   maple env step libero-xyz \
       -a [0.01, -0.02, 0.05, 0.0, 0.0, 0.0, 1.0]

Output:

.. code-block:: text

   Step result:
     Reward: 0.0000
     Terminated: False
     Truncated: False
     Success: False

info
----

Info about the environment setup in the container.

.. code-block:: bash

   maple env info ENV_ID [OPTIONS]

Arguments
^^^^^^^^^

``ENV_ID``
    ID of environment to get the info

Options
^^^^^^^

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)

Example
^^^^^^^

.. code-block:: bash

   maple env info libero-xyz

Output:

.. code-block:: text

   Environment Info:
    Task: LIVING_ROOM_SCENE2_put_both_the_alphabet_soup_and_the_tomato_sauce_in_the_basket
    Suite: libero_10
    Instruction: put both the alphabet soup and the tomato sauce in the basket
    Action space: {'type': 'tuple', 'repr': '(array([-1., -1., -1., -1., -1., -1., -1.]), array([1., 1., 1., 1., 1., 1., 1.]))'}

Notes
^^^^^
- You need to ``setup`` the environment first before calling ``info``. 

stop
----

Stop an environment container.

.. code-block:: bash

   maple env stop ENV_ID [OPTIONS]

Arguments
^^^^^^^^^

``ENV_ID``
    ID of environment to stop

Options
^^^^^^^

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)

Example
^^^^^^^

.. code-block:: bash

   maple env stop libero-xyz

Output:

.. code-block:: text

   ✓ Stopped: libero-xyz

tasks
----

Get the list of tasks in the specific environment suite.

.. code-block:: bash

   maple env tasks backend [OPTIONS]

Arguments
^^^^^^^^^

``BACKEND``
    Environment backend to load

Options
^^^^^^^

``--suite TEXT``
    If the environment have specific suites as well 

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)

Example
^^^^^^^

.. code-block:: bash

   maple env tasks libero --suite libero_10

Output:

.. code-block:: text

   libero_10
    [0] LIVING_ROOM_SCENE2_put_both_the_alphabet_soup_and_the_tomato_sauce_in_the_basket
        → put both the alphabet soup and the tomato sauce in the basket
    [1] LIVING_ROOM_SCENE2_put_both_the_cream_cheese_box_and_the_butter_in_the_basket
        → put both the cream cheese box and the butter in the basket
    [2] KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it
        → turn on the stove and put the moka pot on it
    [3] KITCHEN_SCENE4_put_the_black_bowl_in_the_bottom_drawer_of_the_cabinet_and_close_it
        → put the black bowl in the bottom drawer of the cabinet and close it
    [4] LIVING_ROOM_SCENE5_put_the_white_mug_on_the_left_plate_and_put_the_yellow_and_white_mug_on_the_right_plate
        → put the white mug on the left plate and put the yellow and white mug on the right plate
    [5] STUDY_SCENE1_pick_up_the_book_and_place_it_in_the_back_compartment_of_the_caddy
        → pick up the book and place it in the back compartment of the caddy
    [6] LIVING_ROOM_SCENE6_put_the_white_mug_on_the_plate_and_put_the_chocolate_pudding_to_the_right_of_the_plate
        → put the white mug on the plate and put the chocolate pudding to the right of the plate
    [7] LIVING_ROOM_SCENE1_put_both_the_alphabet_soup_and_the_cream_cheese_box_in_the_basket
        → put both the alphabet soup and the cream cheese box in the basket
    [8] KITCHEN_SCENE8_put_both_moka_pots_on_the_stove
        → put both moka pots on the stove
    [9] KITCHEN_SCENE6_put_the_yellow_and_white_mug_in_the_microwave_and_close_it
        → put the yellow and white mug in the microwave and close it
