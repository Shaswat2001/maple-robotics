import numpy as np
from typing import List, Dict, Any
from maple.adapters.base import Adapter
        
class Gr00tN15BridgeAdapter(Adapter):    
    """
    Gr00tN15BridgeAdapter.
    """
    name: str = "gr00tn15:bridge"
    env: str = "bridge"
    policy: str = "gr00tn15"
    image_key: Dict[str, str] = {"video.image_0":"image"}
    image_size = (256, 256)

    def __init__(self):
        self.default_rot = np.array([[0, 0, 1.0], [0, 1.0, 0], [-1.0, 0, 0]])  
        self.action_scale = 1.0

    def transform_obs(self, raw_obs: Dict[str, Any]) -> Dict[str, Any]:
        """Method to transform libero observation to Gr00t input

        :param raw_obs: Raw observation from libero
        :return: Tranformed observatation as needed by Gr00t
        """
        payload = {}
        for vla_key, key in self.image_key.items():

            image = self.decode_image(raw_obs[key])
            image = self.resize_image(image, self.image_size)
            image = self.rotate_image(image)
            payload[vla_key] = image


        eef_pos= np.array(raw_obs["agent"]['data']["eef_pos"]['data'])
        rm_bridge = self.quat2mat(eef_pos[3:7])
        rpy_bridge_converted = self.mat2euler(rm_bridge @ self.default_rot.T)
        
        payload["state.x"] = eef_pos[0:1].tolist()
        payload["state.y"] = eef_pos[1:2].tolist()
        payload["state.z"] = eef_pos[2:3].tolist()
        payload["state.roll"] = rpy_bridge_converted[0:1].tolist()
        payload["state.pitch"] = rpy_bridge_converted[1:2].tolist()
        payload["state.yaw"] = rpy_bridge_converted[2:3].tolist()
        payload["state.pad"] = [[1]]
        payload["state.gripper"] = eef_pos[7:8].tolist()
              
        return payload
    
    def transform_action(self, raw_action: List[float]) -> List[float]:
        """Method to transform Gr00t output to libero action.
        
        :param raw_action: Raw output from Gr00t.
        :return: Tranformed action needed by the libero.
        """
        raw_action[-1] = self.normalize_gripper_action(raw_action[-1])
        return raw_action.tolist()
    
    def _postprocess_gripper(self, action):
        # trained with [0, 1], 0 close, 1 open -> convert to SimplerEnv [-1, 1]
        return 2.0 * (action > 0.5) - 1.0