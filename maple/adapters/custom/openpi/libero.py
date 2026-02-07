import numpy as np
from typing import List, Dict, Any
from maple.adapters.base import Adapter

class OpenPILiberoAdapter(Adapter):    

    name: str = "openpi:libero"
    env: str = "libero"
    policy: str = "openpi"
    image_key: Dict[str, str] = {"observation/image":"agentview_image", "observation/wrist_image": "robot0_eye_in_hand_image"}
    image_size = (224, 224)

    def transform_obs(self, raw_obs: Dict[str, Any]) -> Dict[str, Any]:
        
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
        return raw_action