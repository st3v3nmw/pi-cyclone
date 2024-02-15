# Pi Cyclone

This is a script to control the active cooler fan on a Raspberry Pi 5.

At the time of writing, I'm running Ubuntu Server 23.10 and there have been
issues integrating with the fan:

1. [Fan speed control not working on Pi 5 under Ubuntu 23.10](https://bugs.launchpad.net/ubuntu/+source/linux-raspi/+bug/2041741) - Fixed
2. [Fan toggles on/off repeatedly](https://bugs.launchpad.net/ubuntu/+source/linux-raspi/+bug/2044341) - Fixed

The 2nd issue means that hysteresis is not working and the fan keeps going on and off at around 50°C. With a 5°C hysteresis,
the fan is turned on at 50°C, it runs until the Pi cools down to 45°C. Without hysteresis, the fan turns off immediately
the temperature goes below 50°C. A few seconds later, the Pi heats up a little and the fan turns on again... You get the idea.

Here are the results while my Pi 5 4GB is idle-ish (running home assistant on Docker Swarm, connected to the official active cooler fan and a 256GB SSD through a USB3.0 to SATA interface):

|                | Min (°C) | Mean (°C) | Max (°C) |
| :------------- | -------: | --------: | -------: |
| No  hysteresis |     48.0 |      49.4 |     50.7 |
| 5°C hysteresis |     44.1 |      47.2 |     50.1 |

## Setup

_(most of these actions require root access)_

Install `pinctrl` from [here](https://github.com/raspberrypi/utils) if you don't have it already:

```console
$ sudo apt-get update && sudo apt-get install build-essential cmake
$ git clone https://github.com/raspberrypi/utils.git
$ cd utils/pinctrl
$ cmake .
$ make
$ sudo make install
```

## Install

Copy the `cyclone.py` script in this repository to your Raspberry Pi. You can use the secure copy protocol (scp) if you're doing this via SSH.

Make it executable:

```console
$ sudo chmod +x cyclone.py
```

Create a service template (change the path to point to where you've stored the `cyclone.py` script):

```
[Unit]
Description = Pi Cyclone

[Service]
Type = simple
ExecStart = python3 /home/stephen/cyclone.py
User = root
Group = root
Restart = on-failure
SyslogIdentifier = pi-cyclone
RestartSec = 5
TimeoutStartSec = infinity

[Install]
WantedBy = multi-user.target
```

Save the file as `pi-cyclone.service` and place the file in your daemon service folder (usually `/etc/systemd/system/`).

Enable the service to start on boot and start it:

```console
$ sudo systemctl enable pi-cyclone
Created symlink /etc/systemd/system/multi-user.target.wants/pi-cyclone.service → /etc/systemd/system/pi-cyclone.service.
$ sudo systemctl daemon-reload
$ sudo systemctl start pi-cyclone
```

To check that the script is running, run:

```console
$ sudo systemctl status pi-cyclone
● pi-cyclone.service - Pi Cyclone
     Loaded: loaded (/etc/systemd/system/pi-cyclone.service; enabled; preset: enabled)
     Active: active (running) since Sun 2024-01-14 13:18:24 EAT; 1min 30s ago
   Main PID: 40454 (python3)
      Tasks: 1 (limit: 4592)
     Memory: 6.2M
        CPU: 104ms
     CGroup: /system.slice/pi-cyclone.service
             └─40454 python3 /home/stephen/cyclone.py

Jan 14 13:18:24 luna systemd[1]: Started pi-cyclone.service - Pi Cyclone.
Jan 14 13:18:24 luna pi-cyclone[40454]: 2024-01-14 13:18:24 INFO: Temperature = 51.6°C, current speed = 0%, new speed = 30%
```

Here are some logs after running `stress --cpu 4` and letting the Pi cool down:

```console
$ cat /var/log/pi-cyclone.log
2024-01-14 13:18:24 INFO: Temperature = 51.6°C, current speed = 0%, new speed = 30%
2024-01-14 13:21:40 INFO: Temperature = 44.4°C, current speed = 30%, new speed = 0%
2024-01-14 13:24:05 INFO: Temperature = 53.8°C, current speed = 0%, new speed = 30%
2024-01-14 13:24:35 INFO: Temperature = 60.4°C, current speed = 30%, new speed = 50%
2024-01-14 13:24:50 INFO: Temperature = 52.7°C, current speed = 50%, new speed = 30%
2024-01-14 13:28:05 INFO: Temperature = 44.4°C, current speed = 30%, new speed = 0%
```

You can check the CPU temperature yourself by running:

```console
$ vcgencmd measure_temp
temp=46.6'C
```

To customize the setting while running the script, use the following options:

```console
$ /home/stephen/cyclone.py --help
usage: cyclone.py [-h] [--low_speed_temp LOW_SPEED_TEMP] [--med_speed_temp MED_SPEED_TEMP] [--high_speed_temp HIGH_SPEED_TEMP] [--full_speed_temp FULL_SPEED_TEMP] [--hysteresis HYSTERESIS]

options:
  -h, --help            show this help message and exit
  --low_speed_temp LOW_SPEED_TEMP
                        Low fan speed temperature threshold (°C)
  --med_speed_temp MED_SPEED_TEMP
                        Medium fan speed temperature threshold (°C)
  --high_speed_temp HIGH_SPEED_TEMP
                        High fan speed temperature threshold (°C)
  --full_speed_temp FULL_SPEED_TEMP
                        Full fan speed temperature threshold (°C)
  --hysteresis HYSTERESIS
                        Hysteresis (°C)
```

### Details

The script will run the following during operation (not necessarily in order):

Unload the `pwm_fan` driver:

```console
$ sudo rmmod pwm_fan
```

You can then export and activate the pwm channel:

```console
$ pinctrl FAN_PWM
45: a0    pd | hi // FAN_PWM/GPIO45 = PWM1_CHAN3
$ cd /sys/class/pwm/pwmchip0
$ echo 3 > export
```

You should now see `/sys/class/pwm/pwmchip0/pwm3`:

```console
$ cd /sys/class/pwm/pwmchip0/pwm3 && ls
capture  duty_cycle  enable  period  polarity  power  uevent
```

Finally, you need to enable the channel:

```console
$ echo 1 > enable
```

We're now be able to control the fan speed by updating the `duty_cycle`:

```console
$ echo 10000 > duty_cycle
```

The maximum `duty_cycle` is:

```console
$ cat period
41566
```

Credits to [this StackExchange answer](https://raspberrypi.stackexchange.com/a/145563) for the setup instructions.

## Uninstall

Stop & disable the service:

```console
$ sudo systemctl disable pi-cyclone
$ sudo systemctl stop pi-cyclone
```

Clean up the files:

```console
$ sudo rm /etc/systemd/system/pi-cyclone.service
$ rm /home/stephen/cyclone.py
```

Disable the pwm channel:

```console
$ cd /sys/class/pwm/pwmchip0/pwm3
$ echo 0 > enable
```

Load the `pwm_fan` driver:

```console
$ sudo modprobe pwm_fan
```

Restart!

## Resources

- [Cooling Raspberry Pi 5](https://www.raspberrypi.com/documentation/computers/raspberry-pi-5.html#cooling-raspberry-pi-5)
- [Heating and cooling Raspberry Pi 5](https://www.raspberrypi.com/news/heating-and-cooling-raspberry-pi-5/)
- [Disable automatic fan speed control of the Raspberry Pi 5 to control it manually](https://raspberrypi.stackexchange.com/questions/145514/disable-automatic-fan-speed-control-of-the-raspberry-pi-5-to-control-it-manually)
- [Manual fancontrol on Raspberry Pi 5 for Ubuntu 23.10 64bit](https://gist.github.com/s-geissler/89d2dbe8ee75e67aaadf5c870cf9291e)
