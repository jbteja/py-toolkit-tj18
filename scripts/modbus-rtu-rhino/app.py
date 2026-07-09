#!/usr/bin/env python

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import yaml
try:
    from pymodbus.client import ModbusSerialClient
    from pymodbus.exceptions import ModbusException

except ImportError:
    print("Error: pymodbus library is required. Install with 'pip install pymodbus'")
    sys.exit(1)

# Parent directory to sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.logger import get_logger

logger = get_logger(__name__)
CONFIG_PATH = Path(__file__).parent / "config.yaml"

class RTUController:
    """Motor controller interface."""

    def __init__(self, port, config, slave_id=None, baudrate=None):
        self.port = port
        self.config = config
        self.comm_params = config.get("communication", {})
        self.modbus_cfg = config.get("modbus", {})
        self.registers = config.get("registers", {})
        self.commands = config.get("commands", {})

        # Override baudrate if provided
        if baudrate:
            self.comm_params["baudrate"] = baudrate

        self.slave_id = slave_id or self.modbus_cfg.get("default_slave_id", 1)
        self.input_registers_supported = True

        # Build client
        self.client = ModbusSerialClient(
            port=self.port,
            baudrate=self.comm_params.get("baudrate", 9600),
            parity=self.comm_params.get("parity", "N"),
            stopbits=self.comm_params.get("stop_bits", 1),
            bytesize=self.comm_params.get("data_bits", 8),
            timeout=self.comm_params.get("timeout", 1),
        )

    def connect(self):
        """Establish connection to the controller."""
        if self.client.connect():
            logger.info(f"Connected on port {self.port} (slave ID {self.slave_id})")
            return True
        else:
            logger.error("Failed to connect")
            return False

    def close(self):
        """Close the serial connection."""
        self.client.close()
        logger.info("Connection closed")

    # def _read_register(self, reg_type, reg_addr, scale=1):
    #     """Read a single register and return scaled value."""
    #     try:
    #         if reg_type == "holding":
    #             result = self.client.read_holding_registers(reg_addr, 1, slave=self.slave_id)
    #         elif reg_type == "input":
    #             result = self.client.read_input_registers(reg_addr, 1, slave=self.slave_id)
    #         else:
    #             raise ValueError(f"Unknown register type: {reg_type}")

    #         if result.isError():
    #             logger.error(f"Modbus error reading {reg_type} register {reg_addr}: {result}")
    #             return None
    #         return result.registers[0] * scale

    #     except ModbusException as e:
    #         logger.error(f"Exception reading register: {e}")
    #         return None

    # def _write_register(self, reg_addr, value, scale=1):
    #     """Write a value to a holding register."""
    #     try:
    #         raw_value = int(value / scale)
    #         result = self.client.write_register(reg_addr, raw_value, slave=self.slave_id)
    #         if result.isError():
    #             logger.error(f"Modbus error writing to register {reg_addr}: {result}")
    #             return False
    #         return True

    #     except ModbusException as e:
    #         logger.error(f"Exception writing register: {e}")
    #         return False

    def _read_register(self, reg_type, reg_addr, scale=1):
        """Read a single register and return scaled value."""
        try:
            kwargs = {"count": 1, "device_id": self.slave_id}
            if reg_type == "holding":
                result = self.client.read_holding_registers(reg_addr, **kwargs)
            elif reg_type == "input":
                result = self.client.read_input_registers(reg_addr, **kwargs)
            else:
                raise ValueError(f"Unknown register type: {reg_type}")

            if result.isError():
                if reg_type == "input" and getattr(result, "exception_code", None) == 1:
                    if self.input_registers_supported:
                        logger.warning(
                            "Device rejected input-register reads (illegal function). "
                            "Skipping remaining input registers."
                        )
                        self.input_registers_supported = False
                    return None
                logger.error(f"Modbus error reading {reg_type} register {reg_addr}: {result}")
                return None
            return result.registers[0] * scale
        except Exception as e:
            logger.error(f"Exception reading register: {e}")
            return None

    def _write_register(self, reg_addr, value, scale=1):
        """Write a value to a holding register."""
        try:
            raw_value = int(value / scale)
            result = self.client.write_register(reg_addr, raw_value, device_id=self.slave_id)
            if result.isError():
                logger.error(f"Modbus error writing to register {reg_addr}: {result}")
                return False
            return True
        except ModbusException as e:
            logger.error(f"Exception writing register: {e}")
            return False

    def read_all_registers(self):
        """Read all defined holding and input registers, log them."""
        logger.info("=== Reading all registers ===")

        # Holding registers
        for reg in self.registers.get("holding", []):
            value = self._read_register("holding", reg["addr"], reg.get("scale", 1))
            if value is not None:
                unit = reg.get("unit", "")
                enum = reg.get("enum", {})
                if enum and int(value) in enum:
                    display = f"{value} ({enum[int(value)]})"
                else:
                    display = f"{value}{unit}"

                if reg["name"] == "device_address":
                    actual_slave = int(value) >> 8
                    display = f"{display} (slave id {actual_slave})"

                logger.info(f"  {reg['name']:20} = {display}")

        # Input registers
        if self.input_registers_supported:
            for reg in self.registers.get("input", []):
                value = self._read_register("input", reg["addr"], reg.get("scale", 1))
                if value is not None:
                    unit = reg.get("unit", "")
                    logger.info(f"  {reg['name']:20} = {value}{unit}")
        else:
            logger.info("Skipping input registers because device indicated they are not supported")

        logger.info("=== End of register dump ===")

    def execute_command(self, cmd_name, **kwargs):
        """Execute a named command from the YAML definition."""
        cmd = self.commands.get(cmd_name)
        if not cmd:
            logger.error(f"Command '{cmd_name}' not found in configuration")
            return False

        sequence = cmd.get("sequence", [])
        for step in sequence:
            reg_name = step["register"]
            value_template = step["value"]

            # Find register definition
            reg_def = None
            for reg in self.registers.get("holding", []):
                if reg["name"] == reg_name:
                    reg_def = reg
                    break
            if not reg_def:
                logger.error(f"Register '{reg_name}' not found for command '{cmd_name}'")
                return False

            # Substitute parameters
            if isinstance(value_template, str) and "{{" in value_template:
                for k, v in kwargs.items():
                    value_template = value_template.replace(f"{{{{ {k} }}}}", str(v))
                # Evaluate simple arithmetic (safe for int expressions)
                try:
                    value = eval(value_template, {"__builtins__": {}}, kwargs)  # nosec
                except Exception as e:
                    logger.error(f"Error evaluating value template '{value_template}': {e}")
                    return False
            else:
                value = value_template

            # Write to register
            success = self._write_register(reg_def["addr"], value, reg_def.get("scale", 1))
            if not success:
                logger.error(f"Failed to execute step: write {reg_name}={value}")
                return False
            logger.info(f"Command '{cmd_name}': wrote {reg_name}={value}")

        logger.info(f"Command '{cmd_name}' executed successfully")
        return True


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


def check_port_available(port) -> bool:
    """Check if a serial port exists and can be opened (simple test)."""
    import serial
    try:
        ser = serial.Serial(port, timeout=0.1)
        ser.close()
        return True

    except (serial.SerialException, FileNotFoundError):
        return False


def main():
    parser = argparse.ArgumentParser(description="Motor Controller Tool")
    parser.add_argument("--port", required=True, help="Serial port (e.g., COM3, /dev/ttyUSB0)")
    parser.add_argument("--device", default="rmcs-3001", help="Device type (matches config section)")
    parser.add_argument("--slave-id", type=int, help="Modbus slave ID (overrides config)")
    parser.add_argument("--baudrate", type=int, help="Baud rate (overrides config)")
    parser.add_argument("--action", choices=["read", "enable", "brake", "stop", "set_speed_open", "set_speed_closed",
                                             "set_mode_analog_open", "set_mode_digital_closed", "set_mode_digital_open",
                                             "set_current_limit", "save_config", "sequence"],
                        default="read", help="Action to perform")
    parser.add_argument("--speed", type=int, help="Speed value (for set_speed_open or set_speed_closed)")
    parser.add_argument("--current", type=float, help="Current limit in Amps (for set_current_limit)")

    args = parser.parse_args()

    # Check port availability
    if not check_port_available(args.port):
        logger.error(f"Port {args.port} is not available or cannot be opened")
        sys.exit(1)

    full_config = load_config()
    config = full_config.get(args.device)
    if not config:
        logger.error("Configuration missing for device '%s'", args.device)
        sys.exit(1)

    # Create controller instance
    controller = RTUController(
        port=args.port,
        config=config,
        slave_id=args.slave_id,
        baudrate=args.baudrate
    )

    # Connect
    if not controller.connect():
        sys.exit(1)

    try:
        # Always read all registers first (for status)
        controller.read_all_registers()

        # Perform requested action
        if args.action == "read":
            # Already done
            pass
        elif args.action == "enable":
            controller.execute_command("enable_motor")
        elif args.action == "brake":
            controller.execute_command("brake_motor")
        elif args.action == "stop":
            controller.execute_command("stop_motor")
        elif args.action == "set_speed_open":
            if args.speed is None:
                logger.error("--speed required for set_speed_open")
                sys.exit(1)
            controller.execute_command("set_speed_open_loop", speed=args.speed)
        elif args.action == "set_speed_closed":
            if args.speed is None:
                logger.error("--speed required for set_speed_closed")
                sys.exit(1)
            controller.execute_command("set_speed_closed_loop", speed_hz=args.speed)
        elif args.action == "set_mode_analog_open":
            controller.execute_command("set_mode_analog_open_loop")
        elif args.action == "set_mode_digital_closed":
            controller.execute_command("set_mode_digital_closed_loop")
        elif args.action == "set_mode_digital_open":
            controller.execute_command("set_mode_digital_open_loop")
        elif args.action == "set_current_limit":
            if args.current is None:
                logger.error("--current required for set_current_limit")
                sys.exit(1)
            controller.execute_command("set_current_limit", amps=args.current)
        elif args.action == "save_config":
            # Note: save_configuration requires current slave ID to be known
            # We'll pass current slave ID from controller instance
            controller.execute_command("save_configuration", current_slave_id=controller.slave_id)
        elif args.action == "sequence":
            logger.info("Running custom travel sequence")
            controller.execute_command("set_speed_frequency", speed=40)
            controller.execute_command("set_travel_distance", distance=100)
            controller.execute_command("enable_forward_257")
            time.sleep(3)
            controller.execute_command("brake_motor")

            controller.execute_command("set_speed_frequency", speed=40)
            controller.execute_command("set_travel_distance", distance=100)
            controller.execute_command("enable_reverse_265")
        else:
            logger.error(f"Unknown action: {args.action}")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    finally:
        controller.close()

if __name__ == "__main__":
    main()

