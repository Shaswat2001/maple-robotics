"""
Adapter: OpenPI ↔ AlohaSim

OpenPI
    input:  224×224 RGB top image + end effector state + language instruction
    output: 7-dim action [x y z rx ry rz gripper] for each robot (continuous)

LIBERO
    AlohaSim keys: agentview_image, robot0_eye_in_hand_image, robot0_proprio-state, ...
    action:   14-dim, gripper 1.0 = open, -1.0 = close
"""
import numpy as np
from typing import List, Dict, Any
from maple.adapters.base import Adapter

class OpenPIAlohaSimAdapter(Adapter):    
    """
    OpenPIAlohaSimAdapter.
    """
    name: str = "openpi:alohasim"
    env: str = "alohasim"
    policy: str = "openpi"
    image_key: Dict[str, str] = {"observation.images.top":"overhead_cam"}
    image_size = (224, 224)

    def transform_obs(self, raw_obs: Dict[str, Any]) -> Dict[str, Any]:
        """Method to transform alohasim observation to openPI input

        :param raw_obs: Raw observation from alohasim
        :return: Tranformed observatation as needed by openPI
        """
        payload = {}
        for vla_key, key in self.image_key.items():

            image = self.decode_image(raw_obs[key])
            image = self.resize_image(image, self.image_size)
            image = np.transpose(image, (2, 0, 1))
            payload[vla_key] = image

        payload["observation.state"] = raw_obs["joints_pos"]["data"]
                            
        return payload
    
    def transform_action(self, raw_action: List[float]) -> List[float]:
        """Method to transform openPI output to alohasim action.
        
        :param raw_action: Raw output from openPI.
        :return: Tranformed action needed by the alohasim.
        """
        return raw_action