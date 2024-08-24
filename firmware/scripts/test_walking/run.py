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

from firmware.imu.imu import IMUInterface
from firmware.robot.robot import Robot

RADIANS = False # Use radians for motor positions

class cmd:
    vx = 0.5
    vy = 0.0
    dyaw = 0.0


def pd_control(target_q, q, kp, dq, kd, default):
    """Calculates torques from position commands."""
    return kp * (target_q + default - q) - kd * dq


def run(policy: Any, args: argparse.Namespace) -> None:
    """Run the simple policy.

    Args:
        policy: The policy used for controlling the simulation.

    Returns:
        None
    """
    count_level = 0
    action_scale = 0.25
    dt = 0.001
    num_actions = 20
    clip_observations = 18.
    clip_actions = 18.
    num_single_obs = 65+6
    frame_stack = 15
    num_observations = frame_stack * num_single_obs
    ang_vel = 1.0
    dof_pos = 1.0
    lin_vel = 2.0
    dof_vel = 0.05
    phase = 0.64
    default = np.array([3.12, -1.98 ,-1.38, 1.32, 0 ,-0.28, 1.5, 1.62, 1, -2.2,   3.55, 3.18, 3.24 ,-1, 0.42,  -1.02, 1.38, -3.24, 1.2, 0])
    kps = tau_limit= np.array([212.5 , 212.5 , 127.5 , 212.5 , 127.5 , 127.5 ,  38.25,  38.25,
        38.25,  38.25, 212.5 , 212.5 , 127.5 , 212.5 , 127.5 , 127.5 ,
        38.25,  38.25,  38.25,  38.25])
    kds = np.array([[10, 10, 10, 10, 10, 10, 10,  5,  5,  5, 10, 10, 10, 10, 10, 10, 10, 5,  5,  5]])
    target_q = np.zeros((num_actions), dtype=np.double)
    action = np.zeros((num_actions), dtype=np.double)

    hist_obs = deque()
    for _ in range(frame_stack):
        hist_obs.append(np.zeros([1, num_single_obs], dtype=np.double))

    target_frequency = 100  # Hz
    target_loop_time = 1.0 / target_frequency  # 4 ms

    # Initialize the robot
    robot = Robot(config_path=args.robot_config,setup=args.config_setup)
    robot.zero_out()
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

        cur_pos = {key : np.array(cur_pos[key]) for key in cur_pos}
        cur_vel = {key : np.array(cur_vel[key]) for key in cur_vel}

        if RADIANS:
            cur_pos = {key : np.degrees(cur_pos[key]) for key in cur_pos}
            cur_vel = {key : np.degrees(cur_vel[key]) for key in cur_vel}

        # Ignoring arms for now
        remapped_pos = {
            key : cur_pos[key][[4, 0, 1, 2, 3]] for key in cur_pos
        }

        remapped_vel = {
            key : cur_vel[key][[4, 0, 1, 2, 3]] for key in cur_vel
        }

        q = np.concatenate(
            (remapped_pos["left_arm"],
            remapped_pos["left_leg"],
            remapped_pos["right_leg"],
            remapped_pos["right_arm"],)
        )

        dq = np.concatenate(
            (remapped_vel["left_arm"],
            remapped_vel["left_leg"],
            remapped_vel["right_leg"],
            remapped_vel["right_arm"],)
        )
        imu_data = imu.step(time.time() - imu_dt)
        imu_dt = time.time()
        eu_ang = imu_data[0]

        eu_ang[eu_ang > math.pi] -= 2 * math.pi
        
        print(action)
        print(obs[0, (2*num_actions + 5) : (3 * num_actions + 5)])
        print(2*num_actions+5)
        print(3*num_actions+5)
        print(obs.shape)

        # TODO: Allen, Pfb30 - figure out phase dt logic
        obs[0, 0] = math.sin(2 * math.pi * count_level * dt / phase)
        obs[0, 1] = math.cos(2 * math.pi * count_level * dt / phase)
        obs[0, 2] = cmd.vx * lin_vel
        obs[0, 3] = cmd.vy * lin_vel
        obs[0, 4] = cmd.dyaw * ang_vel
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

        # Generate PD control
        tau = pd_control(target_q, q, kps, dq, kds, default)

        tau = np.clip(tau, -tau_limit, tau_limit)  # Clamp torques

        count_level += 1

        new_positions = {
            "left_arm": np.array([0, 0, 0, 0, 0, 0, 0, 0]),
            "right_arm": np.array([0, 0, 0, 0, 0, 0, 0, 0]),
            "left_leg": target_q[5:10],
            "right_leg": target_q[15:20],
        }

        if RADIANS:
            new_positions = {
                key : np.radians(new_positions[key]) for key in new_positions
            }

        remapped_new_positions = {
            key : new_positions[key][[1, 2, 3, 4, 0]].tolist() for key in new_positions
        }

        robot.set_position(remapped_new_positions)

        # Calculate how long to sleep
        loop_end_time = time.time()
        loop_duration = loop_end_time - loop_start_time
        sleep_time = max(0, target_loop_time - loop_duration)

        # Sleep for the remaining time to achieve 250 Hz
        time.sleep(sleep_time)
        print("Sleep time: ", sleep_time)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Deployment script.")
    parser.add_argument("--load_model", type=str, required=True, help="Run to load from.")
    parser.add_argument("--robot_config", type=str, default="../../robot/config.yaml", help="Path to the robot configuration file.")
    parser.add_argument("--imu_bus", type=int, default=1, help="The I2C bus number for the IMU.")
    parser.add_argument("--config_setup", type=str, default="stompy_mini", help="The setup configuration for the robot.")
    args = parser.parse_args()

    policy = torch.jit.load(args.load_model)
    run(policy, args)
