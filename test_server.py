#!/usr/bin/env python3
"""Test PLATO server."""
import json
import sys
import os

# Import server
sys.path.insert(0, os.path.dirname(__file__))
import server


def test_submit_and_read():
    """Submit a tile, then read it back."""
    db = server.PlatoDB(":memory:")

    # Submit
    result = db.submit_tile(
        room="test-room",
        domain="testing",
        question="Does the test pass?",
        answer="Yes it does, this is a comprehensive test answer that meets minimum length.",
        agent="test-runner"
    )
    assert result["status"] == "accepted", f"Expected accepted, got {result}"
    assert "tile_id" in result

    # Read rooms
    rooms = db.get_rooms()
    assert "test-room" in rooms
    assert rooms["test-room"]["tile_count"] == 1

    # Read room tiles
    tiles = db.get_room("test-room")
    assert len(tiles) == 1
    assert tiles[0]["question"] == "Does the test pass?"

    # Search
    results = db.search("test")
    assert len(results) == 1

    # Stats
    stats = db.get_stats()
    assert stats["total_tiles"] == 1
    assert stats["total_rooms"] == 1

    print("✅ All tests passed")


def test_gate_validation():
    """Test tile gate validation."""
    db = server.PlatoDB(":memory:")

    # Too short
    result = db.submit_tile("r", "d", "q?", "short")
    assert "error" in result

    # Blocked word
    result = db.submit_tile("r", "d", "q?", "This is always the best answer that meets minimum length requirements")
    assert "error" in result
    assert "always" in result["error"]

    # Valid
    result = db.submit_tile("r", "d", "q?", "This is a good answer that avoids absolutes and is long enough")
    assert result["status"] == "accepted"

    print("✅ Gate validation tests passed")


if __name__ == "__main__":
    test_submit_and_read()
    test_gate_validation()
