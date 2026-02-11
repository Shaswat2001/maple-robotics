"""
Adapter: Gr00t ↔ LIBERO

Gr00t
    input:  224×224 RGB image + 224×224 RGB wrist image + end effector state + language instruction
    output: 7-dim action [x y z rx ry rz gripper] (continuous)

LIBERO
    obs keys: agentview_image, robot0_eye_in_hand_image, robot0_proprio-state, ...
    action:   7-dim, gripper 1.0 = open, -1.0 = close
"""
import numpy as np
from typing import List, Dict, Any
from maple.adapters.base import Adapter

class Gr00tN15LiberoAdapter(Adapter):    
    """
    Gr00tLiberoAdapter.
    """
    name: str = "gr00tn15:libero"
    env: str = "libero"
    policy: str = "gr00tn15"
    image_key: Dict[str, str] = {"observation.images.video.image":"agentview_image", "observation.images.video.wrist_image": "robot0_eye_in_hand_image"}
    image_size = (256, 256)

    def transform_obs(self, raw_obs: Dict[str, Any]) -> Dict[str, Any]:
        """Method to transform libero observation to openPI input

        :param raw_obs: Raw observation from libero
        :return: Tranformed observatation as needed by openPI
        """
        payload = {}
        for vla_key, key in self.image_key.items():

            image = self.decode_image(raw_obs[key])
            image = self.resize_image(image, self.image_size)
            image = self.rotate_image(image)
            payload[vla_key] = image


        xyz = np.expand_dims(np.array(raw_obs["robot0_eef_pos"]["data"]), axis=[0])
        rpy = np.expand_dims(self.quat2axisangle(np.array(raw_obs["robot0_eef_quat"]["data"])), axis=[0])
        gripper = np.expand_dims(np.array(raw_obs["robot0_gripper_qpos"]["data"]), axis=[0])
        
        payload["state.x"] = xyz[:, 0:1].astype(np.float64)
        payload["state.y"] = xyz[:, 1:2].astype(np.float64)
        payload["state.z"] = xyz[:, 2:3].astype(np.float64)
        payload["state.roll"] = rpy[:, 0:1].astype(np.float64)
        payload["state.pitch"] = rpy[:, 1:2].astype(np.float64)
        payload["state.yaw"] = rpy[:, 2:3].astype(np.float64)
        payload["state.gripper"] = gripper[:, 0:1].astype(np.float64)
              
        return payload
    
    def transform_action(self, raw_action: List[float]) -> List[float]:
        """Method to transform openPI output to libero action.
        
        :param raw_action: Raw output from openPI.
        :return: Tranformed action needed by the libero.
        """
        action = np.array(raw_action, dtype=np.float64)
        action = self.normalize_gripper_action(action)
        
        return action.tolist()