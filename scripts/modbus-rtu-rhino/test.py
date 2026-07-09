#!/usr/bin/env python
"""
Simple Modbus RTU register reader for RMCS-3001 V2.
Compatible with older pymodbus versions (where unit ID is positional).
"""

import argparse
import sys

# Try to import pymodbus
try:
    from pymodbus.client import ModbusSerialClient
except ImportError:
    print("pymodbus not installed. Run: pip install pymodbus")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Read RMCS-3001 registers")
    parser.add_argument("--port", required=True, help="Serial port (e.g., COM3, /dev/ttyUSB0)")
    parser.add_argument("--slave", type=int, default=1, help="Modbus slave ID (default: 1)")
    parser.add_argument("--baudrate", type=int, default=9600, help="Baud rate (default: 9600)")
    args = parser.parse_args()

    # Create client (no 'method' keyword, use positional)
    try:
        client = ModbusSerialClient(
            port=args.port,
            baudrate=args.baudrate,
            parity='N',
            stopbits=1,
            bytesize=8,
            timeout=1
        )
    except TypeError as e:
        # Some very old versions expect method as first positional
        print(f"Client creation error: {e}")
        print("Try: pip install --upgrade pymodbus")
        sys.exit(1)

    # Connect
    if not client.connect():
        print(f"Failed to connect to {args.port}")
        sys.exit(1)

    print(f"Connected to {args.port}, slave ID {args.slave}\n")

    # Define register ranges (address, name, type)
    holding_regs = [
        (0x00, "Device Address"),
        (0x01, "Status"),
        (0x02, "Error Code"),
        (0x03, "Control (Brake/Enable)"),
        (0x04, "Operation Mode"),
        (0x05, "Open Loop Speed"),
        (0x06, "Frequency Readback"),
        (0x07, "Target Speed (Closed)"),
        (0x08, "Acceleration"),
        (0x09, "Deceleration"),
        (0x0A, "Current Limit"),
    ]

    input_regs = [
        (0x0E, "Bus Voltage"),
        (0x0F, "Motor Current"),
        (0x10, "Temperature"),
        (0x11, "Actual Speed"),
    ]

    # Read holding registers
    print("=== Holding Registers (4xxxx) ===")
    for addr, name in holding_regs:
        try:
            # Positional arguments: address, count, unit
            result = client.read_holding_registers(addr, 1, args.slave)
            if not result.isError():
                value = result.registers[0]
                # Special scaling for certain registers
                if addr == 0x0A:  # Current limit (0.1A per unit)
                    display = f"{value * 0.1:.1f} A"
                elif addr == 0x0E: # Actually input, but just in case
                    display = str(value)
                else:
                    display = str(value)
                print(f"0x{addr:02X} ({name:20}) = {display}")
            else:
                print(f"0x{addr:02X} ({name:20}) = ERROR: {result}")
        except Exception as e:
            print(f"0x{addr:02X} ({name:20}) = EXCEPTION: {e}")

    # Read input registers
    print("\n=== Input Registers (3xxxx) ===")
    for addr, name in input_regs:
        try:
            result = client.read_input_registers(addr, 1, args.slave)
            if not result.isError():
                value = result.registers[0]
                if addr == 0x0E:  # Bus voltage (0.1V)
                    display = f"{value * 0.1:.1f} V"
                elif addr == 0x0F:  # Motor current (0.1A)
                    display = f"{value * 0.1:.1f} A"
                elif addr == 0x10:  # Temperature (°C)
                    display = f"{value} °C"
                else:
                    display = str(value)
                print(f"0x{addr:02X} ({name:20}) = {display}")
            else:
                print(f"0x{addr:02X} ({name:20}) = ERROR: {result}")
        except Exception as e:
            print(f"0x{addr:02X} ({name:20}) = EXCEPTION: {e}")

    client.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
