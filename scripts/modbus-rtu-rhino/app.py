#!/usr/bin/env python

import argparse
import inspect
import sys
import time
from pathlib import Path
from typing import Any

import yaml

try:
    from pymodbus.client import ModbusSerialClient
    from pymodbus.exceptions import ModbusException

except ImportError:
    print("Error: pymodbus library is required, Install with 'pip install pymodbus'")
    sys.exit(1)

# Parent directory to sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from utils.logger import get_logger

    logger = get_logger(__name__)

except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    except FileNotFoundError:
        logger.error("Configuration file '%s' not found", path)
        sys.exit(1)

    except yaml.YAMLError as exc:
        logger.error("Error parsing %s: %s", path, exc)
        sys.exit(1)


def check_port_available(port: str) -> bool:
    """Check if a serial port exists and can be opened"""
    try:
        import serial

        ser = serial.Serial(port, timeout=0.1)
        ser.close()
        return True

    except ImportError:
        logger.warning("pyserial not installed, skipping pre-port check")
        return True

    except (serial.SerialException, FileNotFoundError):
        return False


# ==============================================================================
# BASE CONTROLLER
# ==============================================================================
class BaseController:
    """Handles the raw Modbus serial connection"""

    def __init__(self, port: str, slave_id: int, config: dict[str, Any]):
        self.port = port
        self.slave_id = slave_id
        self.config = config
        self.registers = config.get("registers", {})

        # Build client
        comm = config.get("communication", {})
        self.client = ModbusSerialClient(
            port=port,
            baudrate=comm.get("baudrate", 9600),
            parity=comm.get("parity", "N"),
            stopbits=comm.get("stopbits", 1),
            bytesize=comm.get("bytesize", 8),
            timeout=comm.get("timeout", 1),
        )
        self._slave_param = self.detect_slave_param()

    def detect_slave_param(self) -> str:
        """Inspects active pymodbus method signature to select correct parameter"""
        try:
            sig = inspect.signature(self.client.read_holding_registers)
            for param in ["device_id", "slave", "unit"]:
                if param in sig.parameters:
                    return param

        except Exception:
            logger.warning("Failed to inspect pymodbus signature, using fallback")
        return "slave"  # Safe backward-compatible fallback

    def connect(self) -> bool:
        """Establish connection to the controller"""
        if self.client.connect():
            logger.info(f"Connected on port {self.port} (slave ID {self.slave_id})")
            return True

        logger.error("Failed to connect")
        return False

    def close(self):
        """Close the serial connection"""
        if hasattr(self, "client") and self.client:
            self.client.close()
            logger.info("Connection closed")

    def _read_registers(self, address: int, count: int = 1):
        """Read holding registers using cached signature"""
        kwargs = {self._slave_param: self.slave_id}
        return self.client.read_holding_registers(address, count=count, **kwargs)

    def _write_register(self, address: int, value: int):
        """Write a single register using cached signature"""
        kwargs = {self._slave_param: self.slave_id}
        return self.client.write_register(address=address, value=value, **kwargs)

    def read_safe(
        self, address: int, count: int = 1, retries: int = 3, delay: float = 0.25
    ):
        """Read registers with a small retry loop to handle controller latency."""
        for attempt in range(1, retries + 1):
            response = self._read_registers(address, count=count)
            if response and not response.isError():
                return response
            if attempt < retries:
                time.sleep(delay)
        return response

    def parse_signed_value(self, val: int, reg_data: dict[str, Any]) -> int:
        """Converts unsigned 16-bit words to signed integers if required by config"""
        reg_range = reg_data.get("range", [])
        # Check if the register configuration allows negative bounds
        if (reg_range and reg_range[0] < 0) and val > 32767:
            return val - 65536
        return val

    def write_safe(
        self,
        reg_name: str,
        value: int = 0,
        verbose: bool = False,
        reg_data: dict[str, Any] | None = None,
    ):
        """Write a register with optional before/after read logging"""
        reg_data = reg_data or self.registers.get(reg_name)
        if not reg_data or "address" not in reg_data:
            logger.error(
                "Register definition for '%s' missing in config.yaml", reg_name
            )
            return None

        address = reg_data["address"]

        if verbose:
            self.read_and_print_register(reg_name, reg_data)
            time.sleep(0.1)

        response = self._write_register(address, value)
        if response is None:
            logger.error("Write failed for %s at address 0x%02X", reg_name, address)
            return None

        if response.isError():
            logger.error("Failed to set %s on address 0x%02X", reg_name, address)
            return None

        logger.info("Setting %s to %s (0x%04X)", reg_name, value, value)

        if verbose:
            time.sleep(0.25)
            self.read_and_print_register(reg_name, reg_data)

        return response

    def read_and_print_register(self, reg_name: str, reg_data: dict[str, Any]):
        """Read a single register and log its value in a readable format."""
        address = reg_data.get("address")
        if address is None:
            return None

        try:
            response = self.read_safe(address, 1)

            if response and not response.isError():
                raw_val = response.registers[0]
                val = self.parse_signed_value(raw_val, reg_data)
                display_name = reg_name.replace("_", " ").title()
                logger.info(f"{display_name} Value: {val} (Hex: 0x{raw_val:04X})")
                logger.debug(f"  - Desc:  {reg_data.get('description', '')}")
                return val

            err_detail = getattr(response, "message", "Modbus Error Response")
            logger.error(
                f"• {reg_name}: ERROR reading address 0x{address:02X} -> {err_detail}\n"
            )
            return None

        except Exception as e:
            logger.error(f"• {reg_name}: {e}\n")
            return None

    def print_verbose(self):
        """Read and print the current state of the controller"""
        width = 50
        logger.info("=" * width)
        logger.info("Controller Status".center(width))
        logger.info("=" * width)

        for reg_name, reg_data in self.registers.items():
            if "r" in reg_data.get("access", ""):
                self.read_and_print_register(reg_name, reg_data)

    @classmethod
    def add_cli_args(cls, subparser: argparse.ArgumentParser):
        """Override in subclasses to register device-specific arguments"""
        pass

    def execute_cli(self, args: argparse.Namespace):
        """Override in subclasses to execute device-specific operations"""
        pass


# ==============================================================================
# RHINO RMCS-3001 CONTROLLER
# ==============================================================================
class RhinoRMCS3001(BaseController):
    """Specific logic and overrides for RMCS-3001-V2"""

    @classmethod
    def add_cli_args(cls, subparser: argparse.ArgumentParser):
        """Device-specific CLI options for RMCS-3001"""
        group = subparser.add_argument_group("RMCS-3001 Specific Parameters")

        group.add_argument(
            "-m",
            "--mode",
            type=int,
            choices=[0, 1, 2, 3, 4],
            default=0,
            help="0: Analog Open, 1: Digital Closed, 2: Digital Open, 3: Analog Closed, 4: Analog Closed Min Speed",
        )

        group.add_argument(
            "-a",
            "--action",
            type=int,
            choices=[0, 1, 2],
            help="0: Disable, 1: Enable, 2: Brake",
        )

        group.add_argument(
            "-d",
            "--direction",
            type=int,
            choices=[0, 1],
            help="0: Clockwise (CW), 1: Counter-Clockwise (CCW)",
        )

        group.add_argument(
            "-s",
            "--speed",
            type=int,
            metavar="[0-32767]",
            help="Target Speed value (Hz for Mode 1, or PWM [0-32767] for Modes 2/3)",
        )

        group.add_argument(
            "-l",
            "--limit",
            type=int,
            metavar="[-32767 to 32767]",
            help="Movement length limit (Valid range: -32767 to 32767, Mode 1 only)",
        )

        group.add_argument(
            "-n",
            "--new-id",
            type=int,
            choices=range(1, 248),
            metavar="[1-247]",
            help="New Modbus Slave Address ID (1-247) for reconfiguration",
        )

    def execute_cli(self, args: argparse.Namespace):
        # Update new slave ID
        if args.new_id is not None:
            logger.info(
                "Attempting to change slave ID from %d to %d",
                args.slave_id,
                args.new_id,
            )
            self.set_slave_id(args.new_id, verbose=args.verbose)
            sys.exit(0)

        # Set movement limit
        if args.limit is not None:
            self.set_limit(limit=args.limit, mode=args.mode, verbose=args.verbose)

        # Set speed
        if args.speed is not None:
            self.set_speed(speed=args.speed, mode=args.mode, verbose=args.verbose)

        # Set control packet
        if args.action is not None or args.direction is not None:
            self.set_control(
                mode=args.mode,
                enable=(args.action in (1, 2)),
                brake=(args.action == 2),
                direction_ccw=(args.direction == 1),
                verbose=args.verbose,
            )

        if args.verbose and not any(
            [
                args.new_id is not None,
                args.limit is not None,
                args.speed is not None,
                args.action is not None or args.direction is not None,
            ]
        ):
            self.print_verbose()

    def set_control(
        self,
        mode: int,
        enable: bool = True,
        brake: bool = False,
        direction_ccw: bool = False,
        verbose: bool = False,
    ):
        """Builds the 16-bit packet and writes it to the register"""
        # Control Byte (Lower 8 bits)
        control_byte = 0x00
        if enable:
            control_byte |= 1 << 0

        if brake:
            control_byte |= 1 << 1

        if direction_ccw:
            control_byte |= 1 << 3

        # Mode Byte (Upper 8 bits)
        mode_byte = (mode & 0xFF) << 8

        # Final 16-bit payload
        payload = mode_byte | control_byte
        reg_data = self.config["registers"].get("control_mode", {})

        logger.debug(
            "Control packet: 0x%04X to address 0x%02X",
            payload,
            reg_data.get("address", 0x00),
        )
        logger.info(
            "Setting -> m: %s, e: %s, brk: %s, dir: %s",
            mode,
            enable,
            brake,
            direction_ccw,
        )
        self.write_safe("control_mode", payload, verbose, reg_data)

    def set_speed(self, speed: int, mode: int, verbose: bool = False):
        """
        Sets the target speed or PWM value based on operating mode
        - Mode 1 (Digital Closed Loop Mode): Writes to the frequency register (0x06)
        - Mode 2/3 (Digital Open Loop / Analog Closed Loop): Writes to the PWM register (0x04)
        """
        if mode == 1:
            reg_key = "frequency"
            default_address = 0x06

        elif mode in [2, 3]:
            reg_key = "pwm"
            default_address = 0x04

        else:
            logger.warning(f"Speed tracking not explicitly configured for mode {mode}")
            return  # No action for unsupported modes

        # Fetch configurations from yaml if available
        reg_data = self.registers.get(reg_key, {})
        address = reg_data.get("address", default_address)
        reg_range = reg_data.get("range")

        # Validate bounds from config file safely
        if reg_range and not (reg_range[0] <= speed <= reg_range[1]):
            logger.warning(
                f"Speed: {speed} value is outside the configured boundaries {reg_range}"
            )

        payload = speed & 0xFFFF  # Standardize to 16-bit unsigned
        logger.debug(
            f"Writing {speed} value (Hex: 0x{payload:04X}) to '{reg_key}' register at 0x{address:02X}"
        )

        self.write_safe(reg_key, payload, verbose, reg_data or {"address": address})

    def set_limit(self, limit: int, mode: int, verbose: bool = False):
        """
        Sets the movement or distance length limit register (0x0C)
        Converts negative integers to 16-bit unsigned representations
        """
        if mode != 1:
            logger.warning(
                f"Movement limits are typically restricted to Mode 1, Mode provided: {mode}"
            )
            return  # No action for unsupported modes

        reg_data = self.registers.get("movement_limit", {})
        address = reg_data.get("address", 0x0C)
        reg_range = reg_data.get("range", [-32767, 32767])

        if not (reg_range[0] <= limit <= reg_range[1]):
            logger.warning(
                f"Movement limit {limit} falls outside valid range boundaries {reg_range}"
            )

        # Fast Two's complement conversion using bitwise masking
        payload = limit & 0xFFFF
        logger.debug(
            f"Writing limit {limit} (Unsigned Hex: 0x{payload:04X}) to address 0x{address:02X}"
        )

        self.write_safe(
            "movement_limit", payload, verbose, reg_data or {"address": address}
        )

    def set_slave_id(self, new_id: int, verbose: bool = False):
        """Updates the slave ID for future transactions"""
        try:
            if new_id == self.slave_id:
                logger.info(
                    "New ID is same as the current ID (%d), no change made!", new_id
                )
                return

            # Fetch range bounds from config
            min_val, max_val = self.registers["device_id"]["range"]

            # Properly validate the integer range
            if not (min_val <= new_id <= max_val):
                logger.error(
                    "New ID %d is outside the valid range %s",
                    new_id,
                    self.registers["device_id"]["range"],
                )
                return

            # Format the value to match the controller's requirement
            register_id = (new_id << 8) | 0xFF

            # Write the new slave ID to the controller's register
            self.write_safe(
                "device_id",
                register_id,
                verbose,
                self.registers.get("device_id", {}),
            )
            self.slave_id = new_id
            logger.info("Slave ID successfully updated to %d", self.slave_id)

        except Exception as e:
            logger.error("Failed to update slave ID: %s", e)


# ==============================================================================
# RHINO RMCS-6611 CONTROLLER
# ==============================================================================
class RhinoRMCS6611(BaseController):
    """Specific logic for RMCS-6611"""

    @classmethod
    def add_cli_args(cls, subparser: argparse.ArgumentParser):
        """Device-specific CLI options for RMCS-6611"""
        group = subparser.add_argument_group("RMCS-6611 Specific Parameters")

        group.add_argument(
            "-e",
            "--enable-modbus",
            type=int,
            choices=[1, 2],
            help="1: Enable RS-485 Control, 2: Disable RS-485 Control",
        )

        group.add_argument(
            "-a",
            "--action",
            type=int,
            choices=[0, 1, 2, 3],
            help="0: Stop, 1: Forward, 2: Reverse, 3: Brake",
        )

        group.add_argument(
            "-s",
            "--speed",
            type=int,
            metavar="[0-6000]",
            help="Set motor target speed in RPM (0 to 6000)",
        )

        group.add_argument(
            "-r",
            "--read",
            action="store_true",
            help="Read feedback register values",
        )

    def read_feedback(self):
        """Read and log supported feedback registers from the controller."""
        feedback_keys = ["speed_feedback", "current_feedback", "voltage_feedback"]

        for reg_key in feedback_keys:
            reg_data = self.registers.get(reg_key)
            if not reg_data:
                continue

            if "r" not in reg_data.get("access", ""):
                logger.warning("Register can't be read, skipping!")
                continue

            address = reg_data.get("address")
            if address is None:
                continue

            try:
                response = self._read_registers(address, 1)
                if response and not response.isError():
                    raw_value = response.registers[0]
                    scaled_value = raw_value

                    if reg_key in {"current_feedback", "voltage_feedback"}:
                        scaled_value = raw_value / 10.0

                    logger.info(
                        "%s: %s (%s)",
                        reg_key.replace("_", " ").title(),
                        scaled_value,
                        raw_value,
                    )

                else:
                    logger.error(
                        "Failed to read %s from address 0x%02X",
                        reg_key,
                        address,
                    )

            except Exception as exc:
                logger.error("Failed to read feedback register %s: %s", reg_key, exc)

    def execute_cli(self, args: argparse.Namespace):
        """CLI command dispatcher"""

        # Enable modbus control if requested
        if args.enable_modbus is not None:
            self.write_safe("enable_modbus", args.enable_modbus, args.verbose)

        # Set speed
        if args.speed is not None:
            self.write_safe("set_speed", args.speed, args.verbose)

        # Set motion control
        if args.action is not None:
            self.write_safe("control_motor", args.action, args.verbose)

        # Read feedback values if requested
        if args.read:
            self.read_feedback()

        # If verbose mode requested without specific write actions or explicit read, dump all registers
        if args.verbose and (
            args.enable_modbus is None
            and args.speed is None
            and args.action is None
            and not args.read
        ):
            self.print_verbose()


# ==============================================================================
# CONTROLLER REGISTRY
# ==============================================================================
CONTROLLER_REGISTRY: dict[str, type[BaseController]] = {
    "rmcs-3001": RhinoRMCS3001,
    "rmcs-6611": RhinoRMCS6611,
}


# ==============================================================================
# CLI ARGUMENT PARSER SETUP
# ==============================================================================
def setup_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CLI Tool for Drivers over Modbus RTU")

    # Subparser container for controller commands
    subparsers = parser.add_subparsers(
        dest="device",
        required=True,
        help="Select the controller model",
    )

    # Register each controller dynamically
    for device_name, controller_cls in CONTROLLER_REGISTRY.items():
        subparser = subparsers.add_parser(
            device_name,
            help=f"Control profile for {device_name}",
        )

        # Global serial / connection arguments added to each subcommand
        conn_group = subparser.add_argument_group("Modbus Connection Settings")

        conn_group.add_argument(
            "-p",
            "--port",
            type=str,
            required=True,
            help="Serial port (e.g. COM3, /dev/ttyUSB0)",
        )

        conn_group.add_argument(
            "-i",
            "--slave-id",
            type=int,
            default=1,
            choices=range(1, 248),
            metavar="[1-247]",
            help="Modbus Slave ID (Default: 1)",
        )

        conn_group.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="Read and display register values",
        )

        # Add controller-specific flags
        controller_cls.add_cli_args(subparser)

    return parser.parse_args()


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    controller = None
    try:
        args = setup_args()
        config = load_config()

        # Validate device configuration
        if not config:
            logger.error("Configuration file is empty or missing content")
            sys.exit(1)

        if args.device not in config:
            logger.error("Configuration missing for device profile '%s'", args.device)
            sys.exit(1)

        device_config = config[args.device]
        if not device_config.get("communication") or not device_config.get("registers"):
            logger.error(
                "Incomplete configuration ('communication' or 'registers' missing) for device '%s'",
                args.device,
            )
            sys.exit(1)

        # Validate serial port availability
        if not check_port_available(args.port):
            logger.error(
                "Serial port '%s' is not available or cannot be opened", args.port
            )
            sys.exit(1)

        # Bind the controller based on selected CLI subcommand
        controller_cls = CONTROLLER_REGISTRY[args.device]
        controller = controller_cls(args.port, args.slave_id, config[args.device])

        # Attempt to connect to the controller
        if not controller.connect():
            sys.exit(1)

        # Run controller-specific logic
        controller.execute_cli(args)

    except KeyboardInterrupt:
        logger.info("Interrupted by user, exiting!")

    except Exception as e:
        logger.error("An unexpected error occurred: %s", e)

    finally:
        # Ensure the connection is closed on exit
        if controller:
            controller.close()
