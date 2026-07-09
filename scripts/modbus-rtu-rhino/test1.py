#!/usr/bin/env python
import argparse
import sys

try:
    from pymodbus.client import ModbusSerialClient
except ImportError:
    print("pymodbus not installed. Run: pip install pymodbus")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Read RMCS-3001 registers")
    parser.add_argument("--port", required=True, help="Serial port (e.g., COM3)")
    parser.add_argument("--slave", type=int, default=1, help="Modbus slave ID (default: 1)")
    parser.add_argument("--baudrate", type=int, default=9600, help="Baud rate")
    args = parser.parse_args()

    # For pymodbus 1.x, pass unit in client constructor
    client = ModbusSerialClient(
        port=args.port,
        baudrate=args.baudrate,
        parity='N',
        stopbits=1,
        bytesize=8,
        timeout=1,
        unit=args.slave      # <-- key: unit ID here
    )

    if not client.connect():
        print(f"Failed to connect to {args.port}")
        sys.exit(1)

    print(f"Connected to {args.port}, slave ID {args.slave}\n")

    # Register definitions
    holding_regs = [
        (0x00, "Device Address"),
        (0x01, "Status"),
        (0x02, "Error Code"),
        (0x03, "Control"),
        (0x04, "Operation Mode"),
        (0x05, "Open Loop Speed"),
        (0x06, "Frequency Readback"),
        (0x07, "Target Speed"),
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
    print("=== Holding Registers ===")
    for addr, name in holding_regs:
        try:
            # Only two arguments: address, count (unit already set in client)
            result = client.read_holding_registers(addr, 1)
            if not result.isError():
                value = result.registers[0]
                # Apply scaling where needed
                if addr == 0x0A:
                    display = f"{value * 0.1:.1f} A"
                else:
                    display = str(value)
                print(f"0x{addr:02X} ({name:20}) = {display}")
            else:
                print(f"0x{addr:02X} ({name:20}) = ERROR: {result}")
        except Exception as e:
            print(f"0x{addr:02X} ({name:20}) = EXCEPTION: {e}")

    # Read input registers
    print("\n=== Input Registers ===")
    for addr, name in input_regs:
        try:
            result = client.read_input_registers(addr, 1)
            if not result.isError():
                value = result.registers[0]
                if addr == 0x0E:
                    display = f"{value * 0.1:.1f} V"
                elif addr == 0x0F:
                    display = f"{value * 0.1:.1f} A"
                elif addr == 0x10:
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
