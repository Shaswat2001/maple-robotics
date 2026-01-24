class LiberoEnv:
    name = "libero"

    def info(self) -> dict:
        return {
            "name": self.name,
            "type": "env",
            "tasks": ["PutCarrotOnPlateInScene-v0"],
        }

    def reset(self):
        print("[Libero] reset (stub)")
        return {"image": None}

    def step(self, action):
        print("[Libero] step (stub)", action)
        return {"image": None}, 0.0, True, {}
