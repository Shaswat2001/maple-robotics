Changelog
=========

All notable changes to MAPLE will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.

[Unreleased]
------------

Added
~~~~~

- Initial documentation site
- Read the Docs integration

[0.0.1] - 2026-02-02
--------------------

Added
~~~~~

- Initial release
- Daemon-based architecture for orchestrating policies and environments
- Docker container management for policies and environments
- CLI with Typer for all operations
- OpenVLA policy backend support
- LIBERO environment backend support
- Adapter system for policy-environment bridging
- REST API for programmatic access
- Model weight management with local caching
- Video recording for evaluation rollouts
- Comprehensive state management

Features
~~~~~~~~

- ``maple serve`` - Start/stop daemon
- ``maple pull`` - Download policies and environments
- ``maple serve policy/env`` - Start containerized components
- ``maple run`` - Execute policy evaluations
- ``maple list`` - View running components
- ``maple status`` - Check daemon health

Documentation
~~~~~~~~~~~~~

- Installation guide
- Quick start tutorial
- Architecture overview
- API reference
- Contributing guidelines
