============
Contributing
============

We welcome contributions to Maple! This guide will help you get started.

Development Setup
=================

1. Clone the repository:

.. code-block:: bash

   git clone https://github.com/arenaxlabs/maple.git
   cd maple

2. Create a virtual environment:

.. code-block:: bash

   python -m venv venv
   source venv/bin/activate

3. Install in development mode:

.. code-block:: bash

   pip install -e ".[dev,docs]"

Running Tests
=============

.. code-block:: bash

   pytest tests/

Code Style
==========

We use ``black`` for formatting and ``ruff`` for linting:

.. code-block:: bash

   black maple/
   ruff check maple/

Building Documentation
======================

.. code-block:: bash

   cd docs
   make html

Open ``docs/_build/html/index.html`` in your browser.

Submitting Changes
==================

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

Please include:

- Clear description of changes
- Tests for new functionality
- Documentation updates if needed
