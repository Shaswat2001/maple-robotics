# MAPLE - A unified CLI daemon for evaluating robotics policies across diverse simulation environments

<p align="center">
<img src="./docs/source/assets/MAPLE.svg" alt="MAPLE" width="600" height="100">
</p>

[![GitHub](https://img.shields.io/badge/GitHub-maple-blue?logo=github)](https://github.com/Shaswat2001/maple-robotics.git)
[![PyPI](https://img.shields.io/pypi/v/maple-robotics)](https://pypi.org/project/maple-robotics/)
[![Documentation](https://readthedocs.org/projects/maple-robotics/badge/?version=latest)](https://maple-robotics.readthedocs.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

---

## Why Maple?

Evaluating robotics policies—whether Vision-Language-Action (VLA) models, foundation models, imitation learning policies, or reinforcement learning agents—across different simulation environments is painful:

- **Environment chaos**: Every simulator has its own observation format, action space, and API quirks
- **Dependency hell**: MuJoCo, PyBullet, Isaac Gym, LIBERO—each with conflicting dependencies  
- **Integration tax**: Each policy-environment combination requires custom glue code
- **No standardization**: Comparing policies across environments means rewriting evaluation scripts

**Maple solves this** with a daemon-based architecture that containerizes everything:

```bash
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
```

**That's it.** No dependency conflicts. No custom scripts. Just results.

---

## Features

- 🐳 **Docker-First Architecture** — Every policy and environment runs in its own container
- 🔌 **Adapter System** — Automatic translation between policy outputs and environment inputs
- 📊 **Batch Evaluation** — Run evaluations across multiple tasks, seeds, and configurations
- ⚙️ **Flexible Configuration** — YAML config files, environment variables, or CLI flags
- 🏥 **Health Monitoring** — Background health checks with auto-restart on failure
- 💾 **Persistent State** — SQLite-backed state storage for tracking history

---

## Installation

```bash
pip install maple-robotics
```

### Requirements

- Python 3.10+
- Docker with NVIDIA GPU support
- NVIDIA GPU with CUDA 12.1+

### Build Docker Images

```bash
# Policy images
docker build -t maple/openvla:latest docker/openvla/
docker build -t maple/smolvla:latest docker/smolvla/

# Environment images
docker build -t maple/libero:latest docker/libero/
```

---

## Quick Start

```bash
# 1. Start daemon
maple serve --detach

# 2. Pull and serve policy
maple pull policy openvla:7b
maple serve policy openvla:7b
# Output: Policy ID: openvla-7b-a1b2c3d4

# 3. Pull and serve environment
maple pull env libero
maple serve env libero
# Output: Env ID: libero-x1y2z3w4

# 4. Run evaluation
maple eval openvla-7b-a1b2c3d4 libero-x1y2z3w4 \
    --tasks libero_10 \
    --seeds 0,1,2 \
    --output results/

# 5. View results
maple report results/
```

---

## Supported Policies

| Policy | Variants | Status |
|--------|----------|--------|
| OpenVLA | 7B | ✅ Supported |
| SmolVLA | libero, base | ✅ Supported |
| Octo | base, small | 🚧 Coming Soon |

## Supported Environments

| Environment | Task Suites | Status |
|-------------|-------------|--------|
| LIBERO | libero_10, libero_90, spatial, object, goal | ✅ Supported |
| SimplerEnv | google_robot, widowx | 🚧 Coming Soon |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      maple CLI                          │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                   Maple Daemon                          │
│  ┌───────────┐  ┌───────────┐  ┌─────────────────────┐  │
│  │ Policy    │  │ Env       │  │ Adapter             │  │
│  │ Backends  │  │ Backends  │  │ Registry            │  │
│  └─────┬─────┘  └─────┬─────┘  └─────────────────────┘  │
└────────┼──────────────┼─────────────────────────────────┘
         │              │
         ▼              ▼
┌─────────────────┐  ┌─────────────────┐
│ Policy Container│  │ Env Container   │
│ (Docker + GPU)  │  │ (Docker + X11)  │
└─────────────────┘  └─────────────────┘
```

---

## Configuration

Create `~/.maple/config.yaml`:

```yaml
daemon:
  port: 8000

policy:
  default_device: cuda:0
  attn_implementation: sdpa

containers:
  memory_limit: 32g
  startup_timeout: 300

eval:
  max_steps: 300
  save_video: false
```

Or use environment variables:

```bash
MAPLE_DEVICE=cuda:1 maple serve
```

---

## Documentation

Full documentation: [maple-robotics.readthedocs.io](https://maple-robotics.readthedocs.io)

- [Installation Guide](https://maple-robotics.readthedocs.io/guides/installation.html)
- [Quick Start](https://maple-robotics.readthedocs.io/guides/quickstart.html)
- [CLI Reference](https://maple-robotics.readthedocs.io/commands/serve.html)
- [API Reference](https://maple-robotics.readthedocs.io/api/overview.html)

---

## License

MIT License - see [LICENSE](LICENSE) for details.
