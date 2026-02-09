"""Base adapter."""

import io
import math
import base64
import numpy as np
from PIL import Image
from typing import Any, Dict, List, Tuple

class Adapter:
    """
    Base adapter between an environment and a policy.
    """

    def __init__(self):
        pass
    
    def transform_obs(self, raw_obs: Dict[str, Any]) -> Dict[str, Any]:
        """Abstract method to transform env observation to policy input.
        
        :param raw_obs: Raw observation from the environment.
        :return: Tranformed observation needed by the policy (model).
        """
        raise NotImplementedError
        
    def transform_action(self, raw_action: List[float]) -> List[float]:
        """Abstract method to transform policy output to env action.
        
        :param raw_action: Raw output from the policy.
        :return: Tranformed action needed by the env.
        """
        raise NotImplementedError

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
    
    def quat2axangle(self, quat, identity_thresh=None):
        quat = np.asarray(quat)
        Nq = np.sum(quat**2)
        if not np.isfinite(Nq):
            return np.array([1.0, 0, 0]), float("nan")
        if identity_thresh is None:
            try:
                identity_thresh = np.finfo(Nq.type).eps * 3
            except (AttributeError, ValueError):  # Not a numpy type or not float
                identity_thresh = np.finfo(np.float64).eps * 3
        if Nq < np.finfo(np.float64).eps**2:  # Results unreliable after normalization
            return np.array([1.0, 0, 0]), 0.0
        if Nq != 1:  # Normalize if not normalized
            s = math.sqrt(Nq)
            quat = quat / s
        xyz = quat[1:]
        len2 = np.sum(xyz**2)
        if len2 < identity_thresh**2:
            # if vec is nearly 0,0,0, this is an identity rotation
            return np.array([1.0, 0, 0]), 0.0
        # Make sure w is not slightly above 1 or below -1
        theta = 2 * math.acos(max(min(quat[0], 1), -1))
        return xyz / math.sqrt(len2), theta


    def quat2mat(self, quat: np.ndarray) -> np.ndarray:
        """
        Convert quaternion to rotation matrix.
        
        Args:
            quat: Quaternion in [x, y, z, w] format (4,) array
            
        Returns:
            Rotation matrix (3, 3) array
        """
        # Normalize quaternion
        quat = quat / np.linalg.norm(quat)
        
        x, y, z, w = quat
        
        # Compute rotation matrix elements
        xx = x * x
        yy = y * y
        zz = z * z
        xy = x * y
        xz = x * z
        yz = y * z
        wx = w * x
        wy = w * y
        wz = w * z
        
        mat = np.array([
            [1 - 2*(yy + zz),     2*(xy - wz),     2*(xz + wy)],
            [    2*(xy + wz), 1 - 2*(xx + zz),     2*(yz - wx)],
            [    2*(xz - wy),     2*(yz + wx), 1 - 2*(xx + yy)]
        ])
        
        return mat

    def mat2euler(self, mat: np.ndarray, seq: str = 'xyz') -> np.ndarray:
        """
        Convert rotation matrix to Euler angles.
        
        Args:
            mat: Rotation matrix (3, 3) array
            seq: Sequence of rotations ('xyz', 'zyx', etc.). Default is 'xyz'
            
        Returns:
            Euler angles [roll, pitch, yaw] in radians (3,) array
        """
        # Using XYZ (roll-pitch-yaw) convention by default
        if seq.lower() == 'xyz':
            # Extract euler angles from rotation matrix
            # R = Rz(yaw) * Ry(pitch) * Rx(roll)
            
            sy = np.sqrt(mat[0, 0]**2 + mat[1, 0]**2)
            
            singular = sy < 1e-6
            
            if not singular:
                roll = np.arctan2(mat[2, 1], mat[2, 2])
                pitch = np.arctan2(-mat[2, 0], sy)
                yaw = np.arctan2(mat[1, 0], mat[0, 0])
            else:
                # Gimbal lock case
                roll = np.arctan2(-mat[1, 2], mat[1, 1])
                pitch = np.arctan2(-mat[2, 0], sy)
                yaw = 0
                
            return np.array([roll, pitch, yaw])
        
        elif seq.lower() == 'zyx':
            # ZYX convention (yaw-pitch-roll)
            sy = np.sqrt(mat[0, 0]**2 + mat[1, 0]**2)
            
            singular = sy < 1e-6
            
            if not singular:
                yaw = np.arctan2(mat[1, 0], mat[0, 0])
                pitch = np.arctan2(-mat[2, 0], sy)
                roll = np.arctan2(mat[2, 1], mat[2, 2])
            else:
                yaw = np.arctan2(-mat[0, 1], mat[1, 1])
                pitch = np.arctan2(-mat[2, 0], sy)
                roll = 0
                
            return np.array([roll, pitch, yaw])
        
        else:
            raise ValueError(f"Unsupported sequence: {seq}. Use 'xyz' or 'zyx'")

    def euler2axangle(self, euler: np.ndarray, seq: str = 'xyz') -> np.ndarray:
        """
        Convert Euler angles to axis-angle representation.
        
        Args:
            euler: Euler angles [roll, pitch, yaw] in radians (3,) array
            seq: Sequence of rotations ('xyz', 'zyx', etc.). Default is 'xyz'
            
        Returns:
            Axis-angle representation (3,) array where magnitude is rotation angle
        """
        # Convert quaternion to axis-angle
        return self.quat2axangle(self.euler2quat(euler))
    
    def euler2quat(self, euler):
        
        ai, aj, ak = euler
        firstaxis, parity, repetition, frame = (0, 0, 0, 0)
        _next_axis = [1, 2, 0, 1]
        i = firstaxis + 1
        j = _next_axis[i + parity - 1] + 1
        k = _next_axis[i - parity] + 1

        if frame:
            ai, ak = ak, ai
        if parity:
            aj = -aj

        ai = ai / 2.0
        aj = aj / 2.0
        ak = ak / 2.0
        ci = math.cos(ai)
        si = math.sin(ai)
        cj = math.cos(aj)
        sj = math.sin(aj)
        ck = math.cos(ak)
        sk = math.sin(ak)
        cc = ci * ck
        cs = ci * sk
        sc = si * ck
        ss = si * sk

        q = np.empty((4,))
        if repetition:
            q[0] = cj * (cc - ss)
            q[i] = cj * (cs + sc)
            q[j] = sj * (cc + ss)
            q[k] = sj * (cs - sc)
        else:
            q[0] = cj * cc + sj * ss
            q[i] = cj * sc - sj * cs
            q[j] = cj * ss + sj * cc
            q[k] = cj * cs - sj * sc
        if parity:
            q[j] *= -1.0

        return q

    def euler2mat(self, euler: np.ndarray, seq: str = 'xyz') -> np.ndarray:
        """
        Convert Euler angles to rotation matrix.
        
        Args:
            euler: Euler angles [roll, pitch, yaw] in radians (3,) array
            seq: Sequence of rotations ('xyz', 'zyx', etc.). Default is 'xyz'
            
        Returns:
            Rotation matrix (3, 3) array
        """
        roll, pitch, yaw = euler
        
        # Individual rotation matrices
        Rx = np.array([
            [1, 0, 0],
            [0, np.cos(roll), -np.sin(roll)],
            [0, np.sin(roll), np.cos(roll)]
        ])
        
        Ry = np.array([
            [np.cos(pitch), 0, np.sin(pitch)],
            [0, 1, 0],
            [-np.sin(pitch), 0, np.cos(pitch)]
        ])
        
        Rz = np.array([
            [np.cos(yaw), -np.sin(yaw), 0],
            [np.sin(yaw), np.cos(yaw), 0],
            [0, 0, 1]
        ])
        
        if seq.lower() == 'xyz':
            # R = Rz * Ry * Rx
            return Rz @ Ry @ Rx
        elif seq.lower() == 'zyx':
            # R = Rx * Ry * Rz
            return Rx @ Ry @ Rz
        else:
            raise ValueError(f"Unsupported sequence: {seq}. Use 'xyz' or 'zyx'")