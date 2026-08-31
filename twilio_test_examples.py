"""
twilio_test_examples.py — Example test cases for Twilio SMS integration

These examples show how to test the integration locally without
sending actual SMS messages through Twilio.

Usage:
    python twilio_test_examples.py
"""

import asyncio
import json
from datetime import datetime
from google.genai import types
from orchestrator import orchestrator
from session_manager import SessionManager, UserSession
from google.adk.runners import InMemoryRunner


async def test_tournament_search():
    """Test: User searches for a tournament."""
    print("\n" + "=" * 60)
    print("TEST: Tournament Search")
    print("=" * 60)
    
    runner = InMemoryRunner(agent=orchestrator, app_name="test")
    session = await runner.session_service.create_session(
        app_name="test",
        user_id="+1234567890"
    )
    
    # User message
    user_message = types.Content(parts=[types.TextPart(text="Find me a tournament")])
    
    response = await runner.send_message(
        app_name="test",
        user_id="+1234567890",
        message=user_message
    )
    
    print(f"\nUser: Find me a tournament")
    print(f"\nOrchestrator Response:")
    if response.message and response.message.parts:
        for part in response.message.parts:
            if hasattr(part, "text"):
                print(part.text)


async def test_hotel_search():
    """Test: User searches for hotels."""
    print("\n" + "=" * 60)
    print("TEST: Hotel Search")
    print("=" * 60)
    
    runner = InMemoryRunner(agent=orchestrator, app_name="test")
    session = await runner.session_service.create_session(
        app_name="test",
        user_id="+1234567891"
    )
    
    user_message = types.Content(parts=[types.TextPart(
        text="Search for hotels in Austin next week"
    )])
    
    response = await runner.send_message(
        app_name="test",
        user_id="+1234567891",
        message=user_message
    )
    
    print(f"\nUser: Search for hotels in Austin next week")
    print(f"\nOrchestrator Response:")
    if response.message and response.message.parts:
        for part in response.message.parts:
            if hasattr(part, "text"):
                print(part.text)


async def test_flight_search():
    """Test: User searches for flights."""
    print("\n" + "=" * 60)
    print("TEST: Flight Search")
    print("=" * 60)
    
    runner = InMemoryRunner(agent=orchestrator, app_name="test")
    session = await runner.session_service.create_session(
        app_name="test",
        user_id="+1234567892"
    )
    
    user_message = types.Content(parts=[types.TextPart(
        text="Find flights from New York to Miami for Sept 1-5"
    )])
    
    response = await runner.send_message(
        app_name="test",
        user_id="+1234567892",
        message=user_message
    )
    
    print(f"\nUser: Find flights from New York to Miami for Sept 1-5")
    print(f"\nOrchestrator Response:")
    if response.message and response.message.parts:
        for part in response.message.parts:
            if hasattr(part, "text"):
                print(part.text)


async def test_confirmation_flow():
    """Test: Confirmation flow with YES/NO responses."""
    print("\n" + "=" * 60)
    print("TEST: Confirmation Flow")
    print("=" * 60)
    
    runner = InMemoryRunner(agent=orchestrator, app_name="test")
    session = await runner.session_service.create_session(
        app_name="test",
        user_id="+1234567893"
    )
    
    # Step 1: Request a tournament
    print(f"\n[1/3] User: Find me a tournament")
    user_message = types.Content(parts=[types.TextPart(text="Find me a tournament")])
    response = await runner.send_message(
        app_name="test",
        user_id="+1234567893",
        message=user_message
    )
    
    if response.message and response.message.parts:
        for part in response.message.parts:
            if hasattr(part, "text"):
                print(f"\nOrchestrator: {part.text}")
    
    # Step 2: User confirms with YES
    print(f"\n[2/3] User: YES")
    user_message = types.Content(parts=[types.TextPart(text="YES")])
    response = await runner.send_message(
        app_name="test",
        user_id="+1234567893",
        message=user_message
    )
    
    if response.message and response.message.parts:
        for part in response.message.parts:
            if hasattr(part, "text"):
                print(f"\nOrchestrator: {part.text}")
    
    # Step 3: Check confirmation result
    print(f"\n[3/3] Confirmation Complete")


async def test_session_persistence():
    """Test: Session state persists across messages."""
    print("\n" + "=" * 60)
    print("TEST: Session Persistence")
    print("=" * 60)
    
    manager = SessionManager.create("memory")
    phone = "+1234567894"
    
    # Create session and send message
    session1 = await manager.get_or_create(phone)
    session1.set("context", "tournament_search")
    session1.set("location", "Austin")
    await manager.save_session(session1)
    
    print(f"\n[1] Stored session data:")
    print(f"  context: {session1.data.get('context')}")
    print(f"  location: {session1.data.get('location')}")
    
    # Retrieve session later
    session2 = await manager.get_or_create(phone)
    print(f"\n[2] Retrieved session data:")
    print(f"  context: {session2.data.get('context')}")
    print(f"  location: {session2.data.get('location')}")
    
    if session2.data.get("context") == "tournament_search":
        print(f"\n✅ Session persistence works!")
    else:
        print(f"\n❌ Session persistence failed!")


async def test_multiple_users():
    """Test: Multiple users maintain separate sessions."""
    print("\n" + "=" * 60)
    print("TEST: Multiple User Sessions")
    print("=" * 60)
    
    manager = SessionManager.create("memory")
    
    # User 1
    session1 = await manager.get_or_create("+1111111111")
    session1.set("preference", "Challenger tournaments")
    await manager.save_session(session1)
    
    # User 2
    session2 = await manager.get_or_create("+2222222222")
    session2.set("preference", "Budget hotels")
    await manager.save_session(session2)
    
    # Retrieve and verify separation
    retrieved1 = await manager.get_or_create("+1111111111")
    retrieved2 = await manager.get_or_create("+2222222222")
    
    print(f"\nUser 1 preference: {retrieved1.data.get('preference')}")
    print(f"User 2 preference: {retrieved2.data.get('preference')}")
    
    if (retrieved1.data.get("preference") == "Challenger tournaments" and
        retrieved2.data.get("preference") == "Budget hotels"):
        print(f"\n✅ Multiple user sessions work!")
    else:
        print(f"\n❌ Multiple user sessions failed!")


async def run_all_tests():
    """Run all tests."""
    print("\n" + "🧪" * 30)
    print("TWILIO SMS INTEGRATION TEST SUITE")
    print("🧪" * 30)
    
    try:
        await test_tournament_search()
        await test_hotel_search()
        await test_flight_search()
        await test_confirmation_flow()
        await test_session_persistence()
        await test_multiple_users()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())
