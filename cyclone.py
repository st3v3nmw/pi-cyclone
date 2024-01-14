#!/usr/bin/env python3

import argparse
from enum import Enum
import logging
from math import floor
import re
import subprocess
from time import sleep

FAN_CTRL_DIR = "/sys/class/pwm/pwmchip0/pwm3/"


logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler("/var/log/pi-cyclone.log", mode="a"),
        logging.StreamHandler(),
    ],
)


parser = argparse.ArgumentParser()
parser.add_argument(
    "--low_speed_temp",
    type=float,
    help="Low fan speed temperature threshold (°C)",
    default=50.0,
)
parser.add_argument(
    "--med_speed_temp",
    type=float,
    help="Medium fan speed temperature threshold (°C)",
    default=60.0,
)
parser.add_argument(
    "--high_speed_temp",
    type=float,
    help="High fan speed temperature threshold (°C)",
    default=67.5,
)
parser.add_argument(
    "--full_speed_temp",
    type=float,
    help="Full fan speed temperature threshold (°C)",
    default=75.0,
)
parser.add_argument(
    "--hysteresis",
    type=float,
    help="Hysteresis (°C)",
    default=5.0,
)
args = parser.parse_args()

assert (
    args.low_speed_temp
    < args.med_speed_temp
    < args.high_speed_temp
    < args.full_speed_temp
    < 80.0
)
assert 2 <= args.hysteresis <= 20


while True:
    with open(FAN_CTRL_DIR + "duty_cycle", "w+") as f:
        with open(FAN_CTRL_DIR + "period", "r") as period_f:
            period = int(period_f.read().strip())

        class FanSpeed(Enum):
            # https://www.raspberrypi.com/documentation/computers/raspberry-pi-5.html#cooling-raspberry-pi-5

            NO_SPIN = 0
            LOW_SPEED = floor(0.3 * period)
            MEDIUM_SPEED = floor(0.5 * period)
            HIGH_SPEED = floor(0.7 * period)
            FULL_SPEED = period

        fan_speed_thresholds = {
            FanSpeed.LOW_SPEED.value: args.low_speed_temp,
            FanSpeed.MEDIUM_SPEED.value: args.med_speed_temp,
            FanSpeed.HIGH_SPEED.value: args.high_speed_temp,
            FanSpeed.FULL_SPEED.value: args.full_speed_temp,
        }

        result = subprocess.run(
            ["vcgencmd", "measure_temp"],
            capture_output=True,
            text=True,
        )
        temperature = float(re.match(r"^temp=(\d*\.\d*)'C", result.stdout)[1])

        curr_state = int(f.read().strip())

        if temperature < args.low_speed_temp:
            target_state = FanSpeed.NO_SPIN
        elif args.low_speed_temp <= temperature < args.med_speed_temp:
            target_state = FanSpeed.LOW_SPEED
        elif args.med_speed_temp <= temperature < args.high_speed_temp:
            target_state = FanSpeed.MEDIUM_SPEED
        elif args.high_speed_temp <= temperature < args.full_speed_temp:
            target_state = FanSpeed.HIGH_SPEED
        else:
            target_state = FanSpeed.FULL_SPEED

        new_state = curr_state
        if curr_state > target_state.value:
            # temperature's going down
            try:
                lower_limit = fan_speed_thresholds[curr_state] - args.hysteresis
                if temperature < lower_limit:
                    new_state = target_state.value
            except KeyError:
                new_state = target_state.value
        else:
            new_state = target_state.value

        if new_state != curr_state:
            f.write(str(new_state))

            logging.info(
                f"Temperature = {temperature}°C, "
                f"current speed = {curr_state/period * 100:.0f}%, "
                f"new speed = {new_state/period * 100:.0f}%"
            )

    sleep(5.0)
