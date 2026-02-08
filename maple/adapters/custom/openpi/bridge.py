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
    image_key: Dict[str, str] = {"observation/primary_image":"image"}
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
        
        eef_pos= np.array(raw_proprio["agent"]['data']["eef_pos"]['data'])
        rm_bridge = self.quat2mat(eef_pos[3:7])
        rpy_bridge_converted = self.mat2euler(rm_bridge @ self.default_rot.T)
        gripper_openness = eef_pos[7] # from simpler, 0 for close, 1 for open
        raw_proprio = np.concatenate([eef_pos[:3], rpy_bridge_converted, np.zeros(1), [gripper_openness]])

        payload["observation/state"] = raw_proprio.tolist()
                            
        return payload
    
    def transform_action(self, raw_action: List[float]) -> List[float]:
        """Method to transform openPI output to libero action.
        
        :param raw_action: Raw output from openPI.
        :return: Tranformed action needed by the libero.
        """
        
        raw_action = {
            "world_vector": np.array(raw_action[:3]),
            "rotation_delta": np.array(raw_action[3:6]),
            "open_gripper": np.array(raw_action[6:7]),
        }

        action = {}
        action["world_vector"] = raw_action["world_vector"] * self.action_scale
        action_rotation_delta = np.asarray(raw_action["rotation_delta"], dtype=np.float64)
        roll, pitch, yaw = action_rotation_delta
        action_rotation_ax, action_rotation_angle = self.euler2axangle(roll, pitch, yaw)
        action_rotation_axangle = action_rotation_ax * action_rotation_angle
        action["rot_axangle"] = action_rotation_axangle * self.action_scale
        action["gripper"] = 2.0 * (raw_action["open_gripper"] > 0.5) - 1.0
        action_conc = np.concatenate([action["world_vector"], action["rot_axangle"], action["gripper"]]).tolist()

        return action_conc