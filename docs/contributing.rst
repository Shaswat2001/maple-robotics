Contributing to MAPLE
=====================

Thank you for your interest in contributing to MAPLE!

Ways to Contribute
------------------

- 🐛 Report bugs
- 💡 Suggest features
- 📝 Improve documentation
- 🔧 Submit bug fixes
- ✨ Add new features
- 🧪 Write tests

Getting Started
---------------

1. Fork and Clone
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   git clone https://github.com/yourusername/maple.git
   cd maple

2. Set Up Development Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

   # Install in editable mode
   pip install -e .

   # Install dev dependencies
   pip install pytest black ruff mypy sphinx sphinx-rtd-theme

3. Build Docker Images
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   docker build -t maple/openvla:latest docker/openvla/
   docker build -t maple/libero:latest docker/libero/

Development Workflow
--------------------

1. Create a Branch
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   git checkout -b feature/your-feature-name

Use prefixes:

- ``feature/`` - New features
- ``fix/`` - Bug fixes
- ``docs/`` - Documentation
- ``refactor/`` - Code refactoring

2. Make Changes
~~~~~~~~~~~~~~~

Follow the project structure::

   maple/
   ├── cmd/           # CLI commands
   ├── server/        # Daemon server
   ├── scheduler/     # Rollout coordination
   ├── backend/       # Policy and environment backends
   ├── adapters/      # Policy-environment adapters
   └── utils/         # Utilities

3. Write Tests
~~~~~~~~~~~~~~

.. code-block:: bash

   # Run tests
   pytest

   # Run specific test
   pytest tests/test_scheduler.py

   # With coverage
   pytest --cov=maple

4. Code Style
~~~~~~~~~~~~~

We use ``black`` for formatting and ``ruff`` for linting:

.. code-block:: bash

   # Format code
   black .

   # Lint
   ruff check .

   # Type checking
   mypy maple/

5. Commit Changes
~~~~~~~~~~~~~~~~~

Use conventional commit messages::

   feat: add support for new environment
   fix: resolve policy loading bug
   docs: update installation guide
   refactor: simplify adapter registry
   test: add scheduler tests

6. Push and Create PR
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   git push origin feature/your-feature-name

Then create a Pull Request on GitHub.

Code Guidelines
---------------

Python Style
~~~~~~~~~~~~

- Follow PEP 8
- Use type hints
- Write docstrings (Google style)
- Keep functions focused and small

**Example:**

.. code-block:: python

   def calculate_reward(
       observation: np.ndarray,
       action: np.ndarray,
       next_observation: np.ndarray
   ) -> float:
       """Calculate reward based on state transition.
       
       Args:
           observation: Current observation
           action: Action taken
           next_observation: Resulting observation
           
       Returns:
           Computed reward value
       """
       # Implementation
       pass

Documentation
~~~~~~~~~~~~~

We use Sphinx for documentation. To build docs locally:

.. code-block:: bash

   cd docs
   make html
   # Open _build/html/index.html

Pull Request Process
--------------------

1. **Update documentation** for any user-facing changes
2. **Add tests** for new functionality
3. **Run all tests** and ensure they pass
4. **Format code** with black and ruff
5. **Update CHANGELOG.rst** with your changes
6. **Create PR** with clear description

PR Description Template
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: markdown

   ## What does this PR do?

   Brief description of changes.

   ## Why is this needed?

   Explain the motivation.

   ## How was this tested?

   Describe testing approach.

   ## Checklist

   - [ ] Tests added/updated
   - [ ] Documentation updated
   - [ ] CHANGELOG.rst updated
   - [ ] Code formatted (black, ruff)
   - [ ] All tests passing

Community
---------

- **Questions?** Open a `Discussion <https://github.com/yourusername/maple/discussions>`_
- **Bug?** Open an `Issue <https://github.com/yourusername/maple/issues>`_

License
-------

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing to MAPLE! 🍁
