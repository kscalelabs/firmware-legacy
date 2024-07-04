"""Example driver file on instantiating new motors and driving them."""

from dataclasses import dataclass

from firmware.bionic_motors.motors import ControlParams


@dataclass
class ViolenceStrength:
    """A class to dictate the strength of the violence."""

    ARM_PARAMS: ControlParams
    GRIPPERS_PARAMS: ControlParams
    # TODO: add more as needed

WEAK_STRENGTH = ViolenceStrength(
    ARM_PARAMS=ControlParams(kp=10, kd=3),
    GRIPPERS_PARAMS=ControlParams(kp=50, kd=2),
    # TODO: add more as needed
)
# Control parameters
NORMAL_STRENGTH = ViolenceStrength(
    ARM_PARAMS=ControlParams(kp=12, kd=5),
    # ARM_PARAMS=ControlParams(kp=100, kd=3),

    GRIPPERS_PARAMS=ControlParams(kp=50, kd=2),
    # TODO: add more as needed
)

MATT_STOMPY_STRENGTH = ViolenceStrength(
    ARM_PARAMS=ControlParams(kp=200, kd=4),
    GRIPPERS_PARAMS=ControlParams(kp=10, kd=2),
    # TODO: Change Params
)
