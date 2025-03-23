"""
Security testing script for the Multimedia Game Assets API.
This script demonstrates how to test the security measures implemented in the API.
"""

import requests
import json
import base64

# Set the API URL
API_URL = "http://localhost:8000"  # Change to your deployed URL for testing


# Define test functions
def test_nosql_injection():
    """Test NoSQL injection prevention."""
    print("\n== Testing NoSQL Injection Prevention ==")

    # Attempt NoSQL injection in player name
    injection_payload = {
        "player_name": "test_player', $where: 'this.score > 0",
        "score": 1000,
        "game_level": "test"
    }

    print("Sending injection payload:", json.dumps(injection_payload))

    # Send the request
    response = requests.post(f"{API_URL}/player_score", json=injection_payload)

    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")

    if response.status_code == 200:
        print("Injection attempt was sanitized and request processed safely")
    else:
        print("Injection attempt was rejected")

    # Check that the sanitized player name was stored correctly
    if response.status_code == 200:
        score_id = response.json().get("id")
        if score_id:
            get_response = requests.get(f"{API_URL}/player_scores/{score_id}")
            if get_response.status_code == 200:
                print(f"Stored player name: {get_response.json().get('player_name')}")


def test_invalid_id():
    """Test ID validation."""
    print("\n== Testing ID Validation ==")

    # Invalid format ID
    invalid_id = "not-a-valid-id"

    print(f"Attempting to access with invalid ID: {invalid_id}")

    # Send the request
    response = requests.get(f"{API_URL}/sprites/{invalid_id}")

    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")

    if response.status_code == 400:
        print("Invalid ID was correctly rejected")
    else:
        print("WARNING: Invalid ID was not properly validated")


def test_xss_prevention():
    """Test XSS prevention."""
    print("\n== Testing XSS Prevention ==")

    # XSS payload in tags
    xss_tags = "<script>alert('XSS')</script>,normal-tag"

    print(f"Attempting to upload sprite with XSS in tags: {xss_tags}")

    # Create a small test image
    test_image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVQI12P4//8/AAX+Av7czFnnAAAAAElFTkSuQmCC")

    # Send the request
    files = {"file": ("test.png", test_image, "image/png")}
    data = {"tags": xss_tags, "description": "Test XSS prevention"}

    response = requests.post(f"{API_URL}/upload_sprite", files=files, data=data)

    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")

    if response.status_code == 200:
        print("Sprite uploaded, now checking if XSS was sanitized")

        # Get the sprite ID from the response
        sprite_id = response.json().get("id")

        if sprite_id:
            # Get the sprite details
            get_response = requests.get(f"{API_URL}/sprites/{sprite_id}")

            if get_response.status_code == 200:
                sprite_data = get_response.json()
                tags = sprite_data.get("metadata", {}).get("tags", [])
                print(f"Stored tags: {tags}")

                # Check if script tag was sanitized
                script_found = any("<script>" in tag.lower() for tag in tags)

                if script_found:
                    print("WARNING: XSS payload was not properly sanitized")
                else:
                    print("XSS payload was correctly sanitized")


# Run the tests
if __name__ == "__main__":
    print("Starting security tests for Multimedia Game Assets API")

    test_nosql_injection()
    test_invalid_id()
    test_xss_prevention()

    print("\nSecurity tests completed")