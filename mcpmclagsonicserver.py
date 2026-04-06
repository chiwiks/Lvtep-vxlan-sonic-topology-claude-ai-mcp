import os
import json
import asyncio
from fastmcp import FastMCP
from dotenv import load_dotenv

from pydantic import Field
from netmiko import ConnectHandler


load_dotenv()
USERNAME  = os.getenv("ROUTER_USERNAME")
PASSWORD  = os.getenv("ROUTER_PASSWORD")



if not USERNAME or not PASSWORD:
    raise RuntimeError("ROUTER_USERNAME / ROUTER_PASSWORD not set")

# Instantiate the FastMCP class
mcp = FastMCP("mcpsonic_lvtep")

INVENTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventory", "networksonic.json")

if not os.path.exists(INVENTORY_FILE):
    raise RuntimeError(f"Inventory file not found: {INVENTORY_FILE}")

with open(INVENTORY_FILE) as f:
    devices = json.load(f)

#Read config tool
@mcp.tool(name="run_show")
async def run_show(
    device: str = Field(..., description="Device name from inventory (e.g. Spine, Leaf1, Leaf2)"),
    command: str = Field(..., description="Show command to execute on the device")
) -> str:
    """ Execute a show command asychronously using Netmiko via SSH"""
    dev = devices.get(device)
    if not dev:
        return f"Unknown device. Available devices are: {list(devices.keys())}"

    connection = {
        "device_type": dev["device_type"],
        "host": dev["host"],
        "username": USERNAME,
        "password": PASSWORD
    }
    loop = asyncio.get_event_loop()
    def _connect():
        conn = ConnectHandler(**connection)
        result = conn.send_command(command)
        conn.disconnect()
        return result

    response = await loop.run_in_executor(None, _connect)
    return response

# Send config tool
@mcp.tool(name="push_config")
async def push_config(
    devices_list: list[str] = Field(..., description="Device names from inventory (e.g. [Spine1,Spine2 Leaf1, Leaf2,Leaf3])"),
    commands: list[str] = Field(..., description="Configuration commands to apply")
) -> dict:
    """Push configuration commands to one or more devices."""
    results = {}
    loop = asyncio.get_event_loop()
    for dev_name in devices_list:
        try:
            device = devices.get(dev_name)
            if not device:
                results[dev_name] = "Unknown device"
                continue
            connection = {
               "device_type": device["device_type"],
               "host": device["host"],
               "username": USERNAME,
               "password": PASSWORD
            }
            def _push():
                conn = ConnectHandler(**connection)
                response = conn.send_config_set(commands)
                conn.disconnect()
                return response
            output = await loop.run_in_executor(None, _push)
            results[dev_name] = {"status": "success", "output": output}
        except Exception as e:
            results[dev_name] = {
                "status": "failed",
                "error": str(e),
            }
    return results

# Run the MCP server
if __name__ == "__main__":
    mcp.run(transport="stdio")
