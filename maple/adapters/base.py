"""Base adapter."""

import io
import math
import base64
import numpy as np
from PIL import Image
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

class Adapter(ABC):
    """
    Base adapter between an environment and a policy.
    """

    def __init__(self):
        pass
    
    @abstractmethod
    def transform_obs(self, raw_obs: Dict[str, Any]) -> Dict[str, Any]:
        """Abstract method to transform env observation to policy input.
        
        :param raw_obs: Raw observation from the environment.
        :return: Tranformed observation needed by the policy (model).
        """
        pass
        
    @abstractmethod
    def transform_action(self, raw_action: List[float]) -> List[float]:
        """Abstract method to transform policy output to env action.
        
        :param raw_action: Raw output from the policy.
        :return: Tranformed action needed by the env.
        """
        pass

    def decode_image(self, image: str) -> Image.Image:
        """Decode base64 image to PIL Image.
        
        :param image: Encoded image (base64 format).
        :return: Decoded PIL image.
        """
        if isinstance(image, dict) and image.get("type") == "image":
            image_b64 = image["data"]
        elif isinstance(image, str):
            image_b64 = image
        else:
            raise ValueError(f"Cannot interpret obs['{key}'] as image (type={type(item)})") 
        
        img_bytes = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(img_bytes))
        return img
    
    def resize_image(self, image: Image.Image, size: Tuple) -> Image.Image:
        """Resize a PIL image to a specific size.
        
        :param image: PIL image.
        :param size: Desired shape of the image.
        :return: Resized PIL image.
        """
        if image.size != size:
            image = image.resize(size, Image.Resampling.LANCZOS)
        return image

    def get_info(self) -> Dict[str, Any]:
        """Get the info of specifc policy-env adapter.
        
        :return: A dictionary containing the adapter information.
        """
        return {
            "name": self.name,
            "policy": self.policy,
            "env": self.env,
            "obs_image_key": self.image_key,
            "obs_image_size": self.image_size,
        }
    
    def rotate_image(self, image: Image.Image) -> Image.Image:
        """Rotate a PIL image by 180 degrees.
        
        :param image: PIL image.
        :return: Rotated PIL image.
        """

        image = image.rotate(180)
        return image

    def normalize_gripper_action(self, action: np.ndarray, binarize: bool= True) -> np.ndarray:
        """Normalize the gripper between 0 and 1.
        
        :param action: A numpy array containing the action.
        :param binarize: If the gripper action is binary value (0/1).
        :return: Action array with normalized gripper value.
        """

        # Just normalize the last action to [-1,+1].
        orig_low, orig_high = 0.0, 1.0
        action[..., -1] = 2 * (action[..., -1] - orig_low) / (orig_high - orig_low) - 1

        if binarize:
            action[..., -1] = np.sign(action[..., -1])

        return action

    def invert_gripper_action(self, action: np.ndarray) -> np.ndarray:
        """Invert the gripper value in the action.
        
        :param action: A numpy array containing the action.
        :return: Action array with inverted gripper value.
        """

        action[..., -1] = action[..., -1] * -1.0
        return action
    
    def quat2axisangle(self, quat: np.ndarray) -> np.ndarray:
        """
        Converts quaternion to axis angle.
        
        :param quat: A numpy array of quaternion.
        :return: Tranformed axis angle equivalent of the quaternion array.
        """
        # clip quaternion
        if quat[3] > 1.0:
            quat[3] = 1.0
        elif quat[3] < -1.0:
            quat[3] = -1.0

        den = np.sqrt(1.0 - quat[3] * quat[3])
        if math.isclose(den, 0.0):
            # This is (close to) a zero degree rotation, immediately return
            return np.zeros(3)

        return (quat[:3] * 2.0 * math.acos(quat[3])) / den