.. _commands-sync:

====
sync
====

Synchronize the database with the filesystem and Docker.

Synopsis
========

.. code-block:: bash

   maple sync policies [OPTIONS]
   maple sync envs [OPTIONS]
   maple sync all [OPTIONS]

Description
===========

The ``sync`` command group reconciles the database with reality:

- **Sync policies**: Check if model weights exist; remove DB entries for missing weights
- **Sync environments**: Check if Docker images exist; remove DB entries for missing images  
- **Sync all**: Run both policy and environment sync operations

Use ``sync`` when you manually delete resources outside of the Maple CLI or want to verify database integrity.

Policy Mode
===========

Check if model weights exist for all policies in the database:

.. code-block:: bash

   maple sync policies [OPTIONS]

Options
-------

``--dry-run``
    Show what would be removed without actually removing

Examples
--------

.. code-block:: bash

   # Preview what would be synced
   maple sync policies --dry-run

   # Sync with confirmation
   maple sync policies

What It Does
------------

1. Gets all policies from database
2. Checks if weights exist at ``~/.maple/models/<name>/<version>/``
3. Reports policies with missing weights
4. Removes database entries for missing policies

Output
------

**All resources present**:

.. code-block:: text

   Scanning policies...
   ✓ All policies in database have weights on disk

**Missing resources detected**:

.. code-block:: text

   Scanning policies...
   
   Found 2 policies with missing weights:
   
   ┌──────────┬─────────┬─────────────────────────────┬─────────┐
   │ Name     │ Version │ Path                        │ Status  │
   ├──────────┼─────────┼─────────────────────────────┼─────────┤
   │ openvla  │ 7b      │ /home/user/.maple/...       │ Missing │
   │ old-model│ v1      │ /home/user/.maple/...       │ Missing │
   └──────────┴─────────┴─────────────────────────────┴─────────┘
   
   Remove 2 policy entries from database? [y/N]: y
   ✓ Removed openvla:7b
   ✓ Removed old-model:v1

**Dry run mode**:

.. code-block:: text

   Scanning policies...
   
   Found 1 policies with missing weights:
   
   ┌─────────┬─────────┬─────────────────────────────┬─────────┐
   │ Name    │ Version │ Path                        │ Status  │
   ├─────────┼─────────┼─────────────────────────────┼─────────┤
   │ openvla │ 7b      │ /home/user/.maple/...       │ Missing │
   └─────────┴─────────┴─────────────────────────────┴─────────┘
   
   Dry run - no changes made

Environment Mode
================

Check if Docker images exist for all environments in the database:

.. code-block:: bash

   maple sync envs [OPTIONS]

Options
-------

``--dry-run``
    Show what would be removed without actually removing

Examples
--------

.. code-block:: bash

   # Preview what would be synced
   maple sync envs --dry-run

   # Sync with confirmation
   maple sync envs

What It Does
------------

1. Gets all environments from database
2. Queries Docker daemon for available images
3. Reports environments with missing images
4. Removes database entries for missing environments

Output
------

**Missing images detected**:

.. code-block:: text

   Scanning environments...
   
   Found 1 environments with missing Docker images:
   
   ┌────────┬─────────────────┬─────────┐
   │ Name   │ Image           │ Status  │
   ├────────┼─────────────────┼─────────┤
   │ libero │ libero:latest   │ Missing │
   └────────┴─────────────────┴─────────┘
   
   Remove 1 environment entries from database? [y/N]: y
   ✓ Removed libero

All Mode
========

Sync both policies and environments in one command:

.. code-block:: bash

   maple sync all [OPTIONS]

Options
-------

``--dry-run``
    Show what would be removed without actually removing

``--yes, -y``
    Auto-confirm all removals

``--port INTEGER``
    Daemon port to connect to (default: from config, typically 8000)

Examples
--------

.. code-block:: bash

   # Preview all sync operations
   maple sync all --dry-run

   # Sync everything
   maple sync all -y

Output
------

.. code-block:: text

   Starting full sync...
   
   1. Syncing Policies
   --------------------------------------------------
   Scanning policies...
   ✓ All policies in database have weights on disk
   
   2. Syncing Environments  
   --------------------------------------------------
   Scanning environments...
   
   Found 1 environments with missing Docker images:
   
   ┌────────┬─────────────────┬─────────┐
   │ Name   │ Image           │ Status  │
   ├────────┼─────────────────┼─────────┤
   │ libero │ libero:latest   │ Missing │
   └────────┴─────────────────┴─────────┘
   
   Remove 1 environment entries from database? [y/N]: y
   ✓ Removed libero
   
   ✓ Sync complete: Removed 1 environment entries
   
   ✓ Full sync complete

Notes
=====

Safety Features
---------------

- **Dry run first**: Always use ``--dry-run`` before making changes to preview what will happen
- **No data loss**: ``sync`` only removes database entries, never actual files or Docker images
- **Safe to run multiple times**: Sync operations are idempotent

Comparison with Remove
----------------------

+------------------+-------------------+-------------------+
| Operation        | sync              | remove            |
+==================+===================+===================+
| Stops containers | ❌ No             | ✅ Yes            |
+------------------+-------------------+-------------------+
| Removes from DB  | ✅ Yes            | ✅ Yes            |
+------------------+-------------------+-------------------+
| Deletes files    | ❌ No             | ✅ Yes (optional) |
+------------------+-------------------+-------------------+
| Deletes images   | ❌ No             | ✅ Yes (optional) |
+------------------+-------------------+-------------------+
| Use case         | After manual      | Clean removal     |
|                  | deletion          | of resources      |
+------------------+-------------------+-------------------+

Decision tree:

.. code-block:: text

   Do you want to delete resources?
   │
   ├─ Yes → Use "maple remove"
   │         ├─ Stops containers
   │         ├─ Removes from DB
   │         └─ Deletes files/images
   │
   └─ No, files already deleted manually → Use "maple sync"
             ├─ Does NOT stop containers  
             ├─ Removes from DB
             └─ Does NOT delete files

Common Use Cases
----------------

**Recovering from manual deletion**:

.. code-block:: bash

   # Manual deletion
   rm -rf ~/.maple/models/openvla/7b/

   # Database still has entry - fix it
   maple sync policies -y

**Docker image cleanup**:

.. code-block:: bash

   # Manual deletion
   docker rmi libero:latest

   # Update database
   maple sync envs -y

**Regular maintenance**:

.. code-block:: bash

   # Weekly maintenance script
   maple sync all --dry-run  # Check first
   maple sync all -y         # Apply if needed

**Before important operations**:

.. code-block:: bash

   # Before starting batch evaluation
   maple sync all --dry-run

   # If issues found, fix them
   maple sync all -y

   # Then proceed with evaluation
   maple eval ...

Error Handling
--------------

**Docker not running**:

.. code-block:: text

   Scanning environments...
   Error connecting to Docker: Cannot connect to the Docker daemon...

Solution: Start Docker and try again.

**Permission issues**:

.. code-block:: text

   Error: Unable to write to database at ~/.maple/state.db

Solution: Check file permissions on ``~/.maple/`` directory.

See Also
========

- :doc:`remove` - Clean removal of resources
- :doc:`list` - List available resources
- :doc:`pull` - Download resources
