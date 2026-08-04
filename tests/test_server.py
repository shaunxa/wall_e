from lego_spike_mcp.server import connection, hub_status


def test_status_is_safe_before_connecting() -> None:
    status = hub_status()
    assert status["connected"] is False
    assert status["mode"] == "discovery-and-connection-only"
    assert connection.status()["address"] is None
