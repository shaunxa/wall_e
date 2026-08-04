# LEGO SPIKE Prime MCP

A local, stdio-based MCP server for a LEGO Education SPIKE Prime hub on macOS.

## Phase 1 scope

This initial build can safely:

- scan for hubs advertising the SPIKE Prime BLE service;
- connect to one hub and subscribe to its notifications;
- report connection status; and
- disconnect.

It intentionally sends **no** movement, program-upload, or raw-protocol commands. That keeps the first hardware test low-risk while we verify your hub, firmware, and macOS Bluetooth permission flow.

## Install and run

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups
uv run lego-spike-mcp
```

The service uses standard input/output, so do not run it in a normal terminal expecting prompts. Configure your MCP client to launch it with:

```json
{
  "mcpServers": {
    "lego-spike": {
      "command": "uv",
      "args": ["--directory", "/Users/shaunxa/Documents/Playground_Lego", "run", "lego-spike-mcp"]
    }
  }
}
```

## First hardware check

1. Charge and power on the SPIKE Prime hub.
2. Close the LEGO SPIKE app if it is connected to the hub—the hub should have one active computer connection.
3. Start the MCP server in your client and call `list_hubs`.
4. Call `connect_hub` using the returned `address`, then `hub_status`.

On first use, macOS may ask the host application for Bluetooth permission. Grant it.

## Protocol basis

The transport uses LEGO's published SPIKE Prime BLE GATT service:

- Service: `0000FD02-0000-1000-8000-00805F9B34FB`
- Hub RX: `0000FD02-0001-1000-8000-00805F9B34FB`
- Hub TX: `0000FD02-0002-1000-8000-00805F9B34FB`

The next phase will add the official protocol handshake, capability discovery, and a constrained `stop_all` implementation before any motor-motion tools.
