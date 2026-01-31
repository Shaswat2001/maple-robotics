import numpy as np
from typing import List, Dict, Any
from vla.adapters.base import Adapter

class OpenVLALiberoAdapter(Adapter):    

    name: str = "openvla:libero"
    env: str = "libero"
    policy: str = "openvla"
    image_key: Dict[str, str] = {"image":"agentview_image"}
    image_size = (224, 224)

    def transform_obs(self, raw_obs: Dict[str, Any]) -> Dict[str, Any]:
        
        payload = {}
        for vla_key, key in self.image_key.items():

            image = self.decode_image(raw_obs[key])
            image = self.resize_image(image, self.image_size)
            image = self.rotate_image(image)
            payload[vla_key] = image
                            
        return payload
    
    def transform_action(self, raw_action: List[float]) -> List[float]:

        action = np.array(raw_action, dtype=np.float64)
        action = self.normalize_gripper_action(action)
        action = self.invert_gripper_action(action)        
        
        return action.tolist()