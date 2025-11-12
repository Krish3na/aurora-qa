import pytest
import requests

BASE_URL = "http://localhost:8000"


def test_health():
    print("\n[TEST] Testing /health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}
    print(f"[PASS] Health check: {data}")


def test_ask_layla_trip():
    print("\n[TEST] Testing: When is Layla planning her trip to London?")
    response = requests.get(f"{BASE_URL}/ask", params={"question": "When is Layla planning her trip to London?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    print(f"[PASS] Answer: {data['answer']}")


def test_ask_vikram_cars():
    print("\n[TEST] Testing: How many cars does Vikram Desai have?")
    response = requests.get(f"{BASE_URL}/ask", params={"question": "How many cars does Vikram Desai have?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    print(f"[PASS] Answer: {data['answer']}")


def test_ask_amira_restaurants():
    print("\n[TEST] Testing: What are Amira's favorite restaurants?")
    response = requests.get(f"{BASE_URL}/ask", params={"question": "What are Amira's favorite restaurants?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    print(f"[PASS] Answer: {data['answer']}")


def test_ask_empty_question():
    print("\n[TEST] Testing empty question (should return 400)...")
    response = requests.get(f"{BASE_URL}/ask", params={"question": ""})
    assert response.status_code == 400
    print(f"[PASS] Correctly rejected empty question with status 400")

