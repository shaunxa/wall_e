"""stdio MCP server exposing safe SPIKE Prime discovery tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .ble import SpikeConnection

mcp = FastMCP("LEGO SPIKE Prime")
connection = SpikeConnection()


@mcp.tool()
async def list_hubs(timeout_seconds: float = 5.0) -> dict:
    """Find nearby SPIKE Prime hubs. Ensure the hub is powered on first."""
    if not 1.0 <= timeout_seconds <= 15.0:
        raise ValueError("timeout_seconds must be between 1 and 15.")
    hubs = await SpikeConnection.scan(timeout_seconds)
    return {"hubs": [hub.to_dict() for hub in hubs]}


@mcp.tool()
async def connect_hub(address: str) -> dict:
    """Connect to a hub returned by list_hubs; this sends no motor commands."""
    return await connection.connect(address)


@mcp.tool()
def hub_status() -> dict:
    """Return the current local BLE connection state and notification count."""
    return connection.status()


@mcp.tool()
async def disconnect_hub() -> dict:
    """Disconnect from the current hub. This Phase 1 server has no motion tools."""
    return await connection.disconnect()


def main() -> None:
    """Start the MCP server over standard input/output."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
