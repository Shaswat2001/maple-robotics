"""
Adapter: OpenVLA ↔ LIBERO

OpenVLA
    input:  224×224 RGB image + language instruction
    output: 7-dim action [x y z rx ry rz gripper] (continuous)

LIBERO
    obs keys: agentview_image, robot0_eye_in_hand_image, robot0_proprio-state, ...
    action:   7-dim, gripper 1.0 = open, -1.0 = close
"""

import numpy as np
from typing import List, Dict, Any
from maple.adapters.base import Adapter

class OpenVLALiberoAdapter(Adapter):    
    """
    OpenVLALiberoAdapter.
    """
    name: str = "openvla:libero"
    env: str = "libero"
    policy: str = "openvla"
    image_key: Dict[str, str] = {"image":"agentview_image"}
    image_size = (224, 224)

    def transform_obs(self, raw_obs: Dict[str, Any]) -> Dict[str, Any]:
        """Method to transform libero observation to openVLA input

        :param raw_obs: Raw observation from libero
        :return: Tranformed observatation as needed by openVLA
        """
        payload = {}
        for vla_key, key in self.image_key.items():

            image = self.decode_image(raw_obs[key])
            image = self.resize_image(image, self.image_size)
            image = self.rotate_image(image)
            payload[vla_key] = image
                            
        return payload
    
    def transform_action(self, raw_action: List[float]) -> List[float]:
        """Method to transform openVLA output to libero action.
        
        :param raw_action: Raw output from openVLA.
        :return: Tranformed action needed by the libero.
        """
        action = np.array(raw_action, dtype=np.float64)
        action = self.normalize_gripper_action(action)
        action = self.invert_gripper_action(action)        
        
        return action.tolist()