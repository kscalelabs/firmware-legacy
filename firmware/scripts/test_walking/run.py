"""Naive deployment script.

Run:
    python firmware/scripts/test_walking --load_model policy.pt
"""

import argparse
import math
import time
from collections import deque
from typing import Any

import numpy as np
import torch

from firmware.motor_utils.motor_utils import CalibrationMode
from firmware.robot.robot import Robot

RADIANS = False  # Use radians for motor positions

# Eyeballed values
# SIM_TO_ROBOT_JOINTS = {
#     # Conversion from sim joint position values to robot joint positions.
#     # Corresponds to "high" position in sim (0 in real)
#     # Ordering is: hip pitch, hip yaw, hip roll, knee pitch, ankle pitch
#     "right_leg": [4.55, 2.24, 4.18, 0, 0.83],
#     "left_leg": [-1.28, 2.62, 0.5, 0, -2.3],
#     "right_arm": [0, 0, 0, 0, 0],
#     "left_arm": [0, 0, 0, 0, 0],
# }

# Values pasted from sim calibration script.
# RESULTS IN:
# Calibrating joint: left ankle pitch
# Position HIGH 0.8200000476837159
# Position LOW -0.9800000834465026
# Calibrating joint: left elbow pitch
# Position HIGH 0.5299999570846559
# Position LOW -0.4499999427795409
# Calibrating joint: left hand gripper
# Position HIGH 2.170000171661377
# Position LOW -0.4000000596046448
# Calibrating joint: left hand roll
# Position HIGH 0.48000007629394537
# Position LOW -0.5000001811981201
# Calibrating joint: left hip pitch
# Position HIGH 1.309984130859375
# Position LOW -1.9651845264434815
# Calibrating joint: left hip roll
# Position HIGH 2.5199998807907105
# Position LOW -2.479999761581421
# Calibrating joint: left hip yaw
# Position HIGH 0.4464770126342774
# Position LOW -1.8952986431121825
# Calibrating joint: left knee pitch
# Position HIGH 1.1099946951866149
# Position LOW -1.4686135196685792
# Calibrating joint: left shoulder pitch
# Position HIGH 0.7910313606262207
# Position LOW 0.027525663375854492
# Calibrating joint: left shoulder roll
# Position HIGH 0.5000046348571776
# Position LOW -0.5099998855590822
# Calibrating joint: left shoulder yaw
# Position HIGH 0.41598587512969964
# Position LOW -2.569994993209839
# Calibrating joint: right ankle pitch
# Position HIGH 1.239999988079071
# Position LOW -0.96
# Calibrating joint: right elbow pitch
# Position HIGH 1.955767651796341
# Position LOW -2.119290599822998
# Calibrating joint: right hand gripper
# Position HIGH 1.733071231842041
# Position LOW -0.6000000596046448
# Calibrating joint: right hand roll
# Position HIGH 0.5009999871253967
# Position LOW -0.5009999871253967
# Calibrating joint: right hip pitch
# Position HIGH 1.0660742187499999
# Position LOW -2.859999999254942
# Calibrating joint: right hip roll
# Position HIGH 1.2499997711181638
# Position LOW -0.9900000000000002
# Calibrating joint: right hip yaw
# Position HIGH 1.5199997711181639
# Position LOW 1.520000247955322
# Calibrating joint: right knee pitch
# Position HIGH 1.387862777709961
# Position LOW -1.15
# Calibrating joint: right shoulder pitch
# Position HIGH 0.04297881126403791
# Position LOW -0.8310000419616701
# Calibrating joint: right shoulder roll
# Position HIGH 0.13099907398223887
# Position LOW -0.2709999227523803
# Calibrating joint: right shoulder yaw
# Position HIGH 1.1000001192092896
# Position LOW -0.26007389426231386

# Operates purely on motor relative calibration, e.g. left vs right joints go opposite dirs
# Offset is the HIGH value for the corresponding joint in SIM_DEFAULT_STANDING_DICT
SIM_TO_ROBOT_JOINTS = {
    "right_leg": [1.0660742187499999, 1.5199997711181639, 1.2499997711181638, 1.387862777709961, 1.239999988079071],
    "left_leg": [1.309984130859375, 0.4464770126342774, 2.5199998807907105, 1.1099946951866149, 0.8200000476837159],
    "right_arm": [0, 0, 0, 0, 0],
    "left_arm": [0, 0, 0, 0, 0],
}

SIM_DEFAULT_STANDING_DICT = {
    "left_hip_pitch": -0.28,
    "left_hip_roll": 1.5,
    "left_hip_yaw": 1.62,
    "left_knee_pitch": 1,
    "left_ankle_pitch": -2.2,
    "right_hip_pitch": 3.55,
    "right_hip_roll": 3.18,
    "right_hip_yaw": 3.23,
    "right_knee_pitch": -1,
    "right_ankle_pitch": 0.42,
}

SIM_DEFAULT_STANDING = {
    "right_leg": [
        SIM_DEFAULT_STANDING_DICT["right_hip_pitch"],
        SIM_DEFAULT_STANDING_DICT["right_hip_yaw"],
        SIM_DEFAULT_STANDING_DICT["right_hip_roll"],
        SIM_DEFAULT_STANDING_DICT["right_knee_pitch"],
        SIM_DEFAULT_STANDING_DICT["right_ankle_pitch"],
    ],
    "left_leg": [
        SIM_DEFAULT_STANDING_DICT["left_hip_pitch"],
        SIM_DEFAULT_STANDING_DICT["left_hip_yaw"],
        SIM_DEFAULT_STANDING_DICT["left_hip_roll"],
        SIM_DEFAULT_STANDING_DICT["left_knee_pitch"],
        SIM_DEFAULT_STANDING_DICT["left_ankle_pitch"],
    ],
    "right_arm": [0, 0, 0, 0, 0],
    "left_arm": [0, 0, 0, 0, 0],
}

"""
        {'left ankle pitch': 9,
        'left elbow pitch': 18,
        'left hip pitch': 5,
        'left hip roll': 7,
        'left hip yaw': 6,
        'left knee pitch': 8,
        'left shoulder pitch': 15,
        'left shoulder roll': 17,
        'left shoulder yaw': 16,
        'left wrist roll': 19,
        'right ankle pitch': 14,
        'right elbow pitch': 3,
        'right hip pitch': 10,
        'right hip roll': 12,
        'right hip yaw': 11,
        'right knee pitch': 13,
        'right shoulder pitch': 0,
        'right shoulder roll': 2,
        'right shoulder yaw': 1,
        'right wrist roll': 4}
      """

DOF_IDS = {
    "left_hip_pitch": 5,
    "left_hip_roll": 7,
    "left_hip_yaw": 6,
    "left_knee_pitch": 8,
    "left_ankle_pitch": 9,
    "right_hip_pitch": 10,
    "right_hip_roll": 12,
    "right_hip_yaw": 11,
    "right_knee_pitch": 13,
    "right_ankle_pitch": 14,
}

ROBOT_TO_ID_MAPPING = {
    0: "hip_pitch",
    1: "hip_yaw",
    2: "hip_roll",
    3: "knee_pitch",
    4: "ankle_pitch",
}


class CMD:
    vx = 0.5
    vy = 0.0
    dyaw = 0.0


def pd_control(
    target_q: np.ndarray, q: np.ndarray, kp: np.ndarray, dq: np.ndarray, kd: np.ndarray, default: np.ndarray
) -> np.ndarray:
    """Calculates torques from position commands."""
    return kp * (target_q + default - q) - kd * dq


def run(policy: Any, args: argparse.Namespace) -> None:
    """Run the simple policy.

    Args:
        policy: The policy used for controlling the simulation.
        args: The arguments passed to the script.

    Returns:
        None
    """
    count_level = 0
    action_scale = 0.25
    dt = 0.001
    num_actions = 20
    clip_observations = 18.0
    clip_actions = 18.0
    num_single_obs = 65 + 6
    frame_stack = 15
    num_observations = frame_stack * num_single_obs
    ang_vel = 1.0
    dof_pos = 1.0
    lin_vel = 2.0
    dof_vel = 0.05
    phase = 0.64
    default = np.array(
        [3.12, -1.98, -1.38, 1.32, 0, -0.28, 1.5, 1.62, 1, -2.2, 3.55, 3.18, 3.24, -1, 0.42, -1.02, 1.38, -3.24, 1.2, 0]
    )
    kps = tau_limit = np.array(
        [
            212.5,
            212.5,
            127.5,
            212.5,
            127.5,
            127.5,
            38.25,
            38.25,
            38.25,
            38.25,
            212.5,
            212.5,
            127.5,
            212.5,
            127.5,
            127.5,
            38.25,
            38.25,
            38.25,
            38.25,
        ]
    )
    kds = np.array([[10, 10, 10, 10, 10, 10, 10, 5, 5, 5, 10, 10, 10, 10, 10, 10, 10, 5, 5, 5]])
    target_q = np.zeros((num_actions), dtype=np.double)
    action = np.zeros((num_actions), dtype=np.double)

    hist_obs = deque()
    for _ in range(frame_stack):
        hist_obs.append(np.zeros([1, num_single_obs], dtype=np.double))

    target_frequency = 100  # Hz
    target_loop_time = 1.0 / target_frequency  # 4 ms

    # Initialize the robot
    robot = Robot(config_path=args.robot_config,setup=args.config_setup, find_can=True, chiral=False)
    #robot.zero_out()

    robot.calibrate_motors(mode=CalibrationMode.FORWARD)

    imu = IMUInterface(args.imu_bus)

    # Calibrate the IMU
    for _ in range(100):
        time.sleep(0.01)
        imu.step(0.01)
        imu.calibrate_yaw()

    imu_dt = time.time()

    while True:
        loop_start_time = time.time()

        # some constant values for the time being
        obs = np.zeros([1, num_single_obs], dtype=np.float32)
        q = default
        dq = np.zeros((num_actions), dtype=np.double)
        omega = np.array([0.15215212, 0.11281695, 0.24282128])
        eu_ang = np.zeros((3), dtype=np.double)

        # TODO:
        cur_pos = robot.get_motor_positions()
        cur_vel = robot.get_motor_speeds()

        """
        q order:
            ankle pitch
            hip pitch
            hip roll
            hip yaw
            knee pitch
        cur_pos / robot position order:
            hip pitch
            hip roll
            hip yaw
            knee pitch
            ankle pitch
      """

        # Convert from robot joint positions to sim joint positions
        cur_pos = {
            key: np.array([SIM_TO_ROBOT_JOINTS[key][i] + cur_pos[key][i] for i in range(len(cur_pos[key]))])
            for key in cur_pos
        }

        cur_pos = {key: np.array(cur_pos[key]) for key in cur_pos}
        cur_vel = {key: np.array(cur_vel[key]) for key in cur_vel}
        cur_pos["left_arm"] = np.array([0, 0, 0, 0, 0])
        cur_vel["left_arm"] = np.array([0, 0, 0, 0, 0])
        cur_pos["right_arm"] = np.array([0, 0, 0, 0, 0])
        cur_vel["right_arm"] = np.array([0, 0, 0, 0, 0])
        if RADIANS:
            cur_pos = {key : np.degrees(cur_pos[key]) for key in cur_pos}
            cur_vel = {key : np.degrees(cur_vel[key]) for key in cur_vel}

        q = np.zeros((num_actions), dtype=np.double)
        dq = np.zeros((num_actions), dtype=np.double)

        for i in range(cur_pos["left_leg"].shape[0]):
            q[DOF_IDS[f"left_{ROBOT_TO_ID_MAPPING[i]}"]] = cur_pos["left_leg"][i]
            dq[DOF_IDS[f"left_{ROBOT_TO_ID_MAPPING[i]}"]] = cur_vel["left_leg"][i]

        for i in range(cur_pos["right_leg"].shape[0]):
            q[DOF_IDS[f"right_{ROBOT_TO_ID_MAPPING[i]}"]] = cur_pos["right_leg"][i]
            dq[DOF_IDS[f"right_{ROBOT_TO_ID_MAPPING[i]}"]] = cur_vel["right_leg"][i]

        imu_data = imu.step(time.time() - imu_dt)
        imu_dt = time.time()
        eu_ang = imu_data[0]

        # eu_ang = np.zeros((3), dtype=np.double)
        eu_ang[eu_ang > math.pi] -= 2 * math.pi

        # TODO: Allen, Pfb30 - figure out phase dt logic
        obs[0, 0] = math.sin(2 * math.pi * count_level * dt / phase)
        obs[0, 1] = math.cos(2 * math.pi * count_level * dt / phase)
        obs[0, 2] = CMD.vx * lin_vel
        obs[0, 3] = CMD.vy * lin_vel
        obs[0, 4] = CMD.dyaw * ang_vel
        obs[0, 5 : (num_actions + 5)] = (q - default) * dof_pos
        obs[0, (num_actions + 5) : (2 * num_actions + 5)] = dq * dof_vel
        obs[0, (2 * num_actions + 5) : (3 * num_actions + 5)] = action
        obs[0, (3 * num_actions + 5) : (3 * num_actions + 5) + 3] = omega
        obs[0, (3 * num_actions + 5) + 3 : (3 * num_actions + 5) + 2 * 3] = eu_ang

        obs = np.clip(obs, -clip_observations, clip_observations)

        hist_obs.append(obs)
        hist_obs.popleft()

        policy_input = np.zeros([1, num_observations], dtype=np.float32)
        for i in range(frame_stack):
            policy_input[0, i * num_single_obs : (i + 1) * num_single_obs] = hist_obs[i][0, :]
        action[:] = policy(torch.tensor(policy_input))[0].detach().numpy()

        action = np.clip(action, -clip_actions, clip_actions)

        target_q = action * action_scale

        print(target_q)

        # Generate PD control
        tau = pd_control(target_q, q, kps, dq, kds, default)

        tau = np.clip(tau, -tau_limit, tau_limit)  # Clamp torques

        count_level += 1

        """
        {'left ankle pitch': 9,
        'left elbow pitch': 18,
        'left hip pitch': 5,
        'left hip roll': 7,
        'left hip yaw': 6,
        'left knee pitch': 8,
        'left shoulder pitch': 15,
        'left shoulder roll': 17,
        'left shoulder yaw': 16,
        'left wrist roll': 19,
        'right ankle pitch': 14,
        'right elbow pitch': 3,
        'right hip pitch': 10,
        'right hip roll': 12,
        'right hip yaw': 11,
        'right knee pitch': 13,
        'right shoulder pitch': 0,
        'right shoulder roll': 2,
        'right shoulder yaw': 1,
        'right wrist roll': 4}
      """

        new_positions = {
            "left_arm": np.array([0, 0, 0, 0, 0]),
            "right_arm": np.array([0, 0, 0, 0, 0]),
            "left_leg": np.array([target_q[DOF_IDS[f"left_{ROBOT_TO_ID_MAPPING[i]}"]] for i in range(5)]),
            "right_leg": np.array([target_q[DOF_IDS[f"right_{ROBOT_TO_ID_MAPPING[i]}"]] for i in range(5)]),
        }

        if RADIANS:
            new_positions = {key: np.radians(new_positions[key]) for key in new_positions}

        set_positions = {key: new_positions[key] for key in new_positions}

        # Subtract the SIM_TO_ROBOT_JOINTS values to get the actual motor positions
        set_positions = {
            key: np.array(
                [
                    set_positions[key][i] - SIM_TO_ROBOT_JOINTS[key][i] + SIM_DEFAULT_STANDING[key][i]
                    for i in range(len(set_positions[key]))
                ]
            )
            for key in set_positions
        }

        print(f"Set positions: {set_positions}")

        # Clamp arms to 0
        set_positions["left_arm"] = np.array([0, 0, 0, 0, 0])
        set_positions["right_arm"] = np.array([0, 0, 0, 0, 0])

        # Clamp arms to defualt standing

        set_positions["left_arm"] = np.array([1, 3.3, 1.6, 1.5, 2])
        set_positions["right_arm"] = np.array([-1, -3.3, -1.6, -1.5, -2])

        set_positions.pop("left_arm")
        set_positions.pop("right_arm")

        robot.set_position(set_positions)

        # Calculate how long to sleep
        loop_end_time = time.time()
        loop_duration = loop_end_time - loop_start_time
        sleep_time = max(0, target_loop_time - loop_duration)

        # Sleep for the remaining time to achieve 250 Hz
        time.sleep(sleep_time)
        # print("Sleep time: ", sleep_time)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deployment script.")
    parser.add_argument("--load_model", type=str, required=True, help="Run to load from.")
    parser.add_argument(
        "--robot_config", type=str, default="../../robot/config.yaml", help="Path to the robot configuration file."
    )
    parser.add_argument("--imu_bus", type=int, default=1, help="The I2C bus number for the IMU.")
    parser.add_argument(
        "--config_setup", type=str, default="stompy_mini", help="The setup configuration for the robot."
    )
    args = parser.parse_args()

    policy = torch.jit.load(args.load_model)
    run(policy, args)
