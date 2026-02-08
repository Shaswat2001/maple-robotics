"""
Adapter: OpenPI ↔ Bridge

OpenPI
    input:  224×224 RGB image + end effector state + language instruction
    output: 7-dim action [x y z rx ry rz gripper] (continuous)

Bridge
    obs keys: agentview_image, robot0_eye_in_hand_image, robot0_proprio-state, ...
    action:   7-dim, gripper 1.0 = open, -1.0 = close
"""
import numpy as np
from typing import List, Dict, Any
from maple.adapters.base import Adapter

class OpenPIBridgeAdapter(Adapter):    
    """
    OpenPIBridgeAdapter.
    """
    name: str = "openpi:bridge"
    env: str = "bridge"
    policy: str = "openpi"
    image_key: Dict[str, str] = {"observation/image":"image"}
    image_size = (224, 224)

    def __init__(self):
        self.default_rot = np.array([[0, 0, 1.0], [0, 1.0, 0], [-1.0, 0, 0]])  
        self.action_scale = 1.0

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

        payload["observation/state"] = np.concatenate([np.array(raw_obs["robot0_eef_pos"]["data"]), 
                                           self.quat2axisangle(np.array(raw_obs["robot0_eef_quat"]["data"])), 
                                           np.array(raw_obs["robot0_gripper_qpos"]["data"])]).tolist()
                            
        return payload
    
    def transform_action(self, raw_action: List[float]) -> List[float]:
        """Method to transform openPI output to libero action.
        
        :param raw_action: Raw output from openPI.
        :return: Tranformed action needed by the libero.
        """
        
        return raw_action