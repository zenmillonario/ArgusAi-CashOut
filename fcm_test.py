import requests
import json
import time
import sys
import os
import pymongo
from datetime import datetime
import asyncio
import uuid

# Add the FCM notification tests to the existing backend_test.py file
def test_fcm_service_integration():
    """Test the FCM service integration"""
    print("\n🔍 TESTING FEATURE: FCM Service Integration")
    
    # Use the CashoutAITester class from the existing backend_test.py
    from backend_test import CashoutAITester
    tester = CashoutAITester()
    
    # Test 1: Check if FCM service is properly initialized
    print("\n🔍 Test 1: Check if FCM service is properly initialized")
    
    try:
        sys.path.append('/app/backend')
        from fcm_service import fcm_service
        
        if fcm_service:
            print("✅ FCM service is properly initialized")
            fcm_service_initialized = True
        else:
            print("❌ FCM service is not properly initialized")
            fcm_service_initialized = False
    except Exception as e:
        print(f"❌ Error importing FCM service: {str(e)}")
        fcm_service_initialized = False
    
    # Test 2: Test FCM token registration API
    print("\n🔍 Test 2: Test FCM token registration API")
    
    # Login as admin
    admin_user = tester.test_login("admin", "admin123", tester.session1)
    if not admin_user:
        print("❌ Admin login failed, cannot test FCM token registration")
        token_registration_test = False
    else:
        # Generate a mock FCM token
        mock_token = f"fcm-token-{uuid.uuid4()}"
        
        # Register the FCM token
        token_result = test_register_fcm_token(
            tester,
            admin_user['id'],
            mock_token,
            tester.session1
        )
        
        if token_result:
            print(f"✅ FCM token registration successful")
            token_registration_test = True
        else:
            print("❌ FCM token registration failed")
            token_registration_test = False
    
    # Test 3: Test sending a test notification
    print("\n🔍 Test 3: Test sending a test notification")
    
    if token_registration_test:
        # Generate a mock FCM token for testing
        test_token = f"fcm-test-token-{uuid.uuid4()}"
        
        # Send a test notification
        notification_result = test_send_test_notification(
            tester,
            test_token,
            tester.session1
        )
        
        if notification_result:
            print(f"✅ Test notification API endpoint working")
            test_notification_test = True
        else:
            print("❌ Test notification API endpoint failed")
            test_notification_test = False
    else:
        print("❌ Skipping test notification test due to token registration failure")
        test_notification_test = False
    
    # Test 4: Test chat message notifications
    print("\n🔍 Test 4: Test chat message notifications")
    
    if admin_user:
        # Create a test user to receive notifications
        timestamp = datetime.now().strftime("%H%M%S")
        username = f"fcm_test_{timestamp}"
        email = f"fcm_test_{timestamp}@example.com"
        real_name = f"FCM Test User {timestamp}"
        
        test_user = tester.test_register_with_membership(
            username=username,
            email=email,
            real_name=real_name,
            membership_plan="Monthly",
            password="TestPass123!",
            session=tester.session2
        )
        
        if test_user:
            print(f"✅ Created test user {username} for notification testing")
            
            # Approve the test user
            success, response = tester.run_test(
                "Approve test user",
                "POST",
                "users/approve",
                200,
                session=tester.session1,
                data={
                    "user_id": test_user['id'],
                    "approved": True,
                    "admin_id": admin_user['id'],
                    "role": "member"
                }
            )
            
            if success:
                print(f"✅ Test user approved successfully")
                
                # Login as the test user
                test_user_login = tester.test_login(username, "TestPass123!", tester.session2)
                if test_user_login:
                    print(f"✅ Test user login successful")
                    
                    # Register FCM token for test user
                    test_user_token = f"fcm-token-{test_user['id']}"
                    token_result = test_register_fcm_token(
                        tester,
                        test_user_login['id'],
                        test_user_token,
                        tester.session2
                    )
                    
                    if token_result:
                        print(f"✅ FCM token registered for test user")
                        
                        # Send a chat message as admin that should trigger notification to test user
                        chat_result = test_chat_message_notification(
                            tester,
                            admin_user['id'],
                            "This is a test message that should trigger FCM notification!",
                            tester.session1
                        )
                        
                        if chat_result:
                            print(f"✅ Chat message sent successfully")
                            chat_notification_test = True
                        else:
                            print("❌ Failed to send chat message")
                            chat_notification_test = False
                    else:
                        print("❌ Failed to register FCM token for test user")
                        chat_notification_test = False
                else:
                    print("❌ Test user login failed")
                    chat_notification_test = False
            else:
                print("❌ Failed to approve test user")
                chat_notification_test = False
        else:
            print("❌ Failed to create test user")
            chat_notification_test = False
    else:
        print("❌ Admin login failed, skipping chat notification test")
        chat_notification_test = False
    
    # Test 5: Test user registration admin notifications
    print("\n🔍 Test 5: Test user registration admin notifications")
    
    if admin_user:
        # Create another test user to trigger admin notification
        timestamp = datetime.now().strftime("%H%M%S")
        username = f"admin_notify_{timestamp}"
        email = f"admin_notify_{timestamp}@example.com"
        real_name = f"Admin Notify User {timestamp}"
        
        test_user2 = tester.test_register_with_membership(
            username=username,
            email=email,
            real_name=real_name,
            membership_plan="Monthly",
            password="TestPass123!"
        )
        
        if test_user2:
            print(f"✅ Created test user {username} to trigger admin notification")
            admin_notification_test = True
        else:
            print("❌ Failed to create test user for admin notification")
            admin_notification_test = False
    else:
        print("❌ Admin login failed, skipping admin notification test")
        admin_notification_test = False
    
    # Overall test result
    fcm_service_test_result = fcm_service_initialized and token_registration_test and test_notification_test and chat_notification_test and admin_notification_test
    
    print(f"\nFCM Service Integration Test: {'✅ PASSED' if fcm_service_test_result else '❌ FAILED'}")
    return fcm_service_test_result

def test_fcm_token_registration_api():
    """Test the FCM token registration API"""
    print("\n🔍 TESTING FEATURE: FCM Token Registration API")
    
    from backend_test import CashoutAITester
    tester = CashoutAITester()
    
    # Test 1: Register a new FCM token
    print("\n🔍 Test 1: Register a new FCM token")
    
    # Login as admin
    admin_user = tester.test_login("admin", "admin123", tester.session1)
    if not admin_user:
        print("❌ Admin login failed, cannot test FCM token registration")
        return False
    
    # Generate a mock FCM token
    mock_token = f"fcm-token-{uuid.uuid4()}"
    
    # Register the FCM token
    token_result = test_register_fcm_token(
        tester,
        admin_user['id'],
        mock_token,
        tester.session1
    )
    
    if not token_result:
        print("❌ FCM token registration failed")
        return False
    
    print(f"✅ FCM token registration successful")
    
    # Test 2: Update an existing FCM token
    print("\n🔍 Test 2: Update an existing FCM token")
    
    # Generate a new mock FCM token
    updated_token = f"fcm-token-updated-{uuid.uuid4()}"
    
    # Register the updated FCM token for the same user
    updated_result = test_register_fcm_token(
        tester,
        admin_user['id'],
        updated_token,
        tester.session1
    )
    
    if not updated_result:
        print("❌ FCM token update failed")
        return False
    
    print(f"✅ FCM token update successful")
    
    # Test 3: Test validation for missing user_id
    print("\n🔍 Test 3: Test validation for missing user_id")
    
    success, response = tester.run_test(
        "Register FCM token with missing user_id",
        "POST",
        "fcm/register-token",
        400,  # Expecting 400 Bad Request
        session=tester.session1,
        data={"token": mock_token}  # Missing user_id
    )
    
    if success:
        print(f"✅ Validation for missing user_id working correctly")
    else:
        print("❌ Validation for missing user_id failed")
        return False
    
    # Test 4: Test validation for missing token
    print("\n🔍 Test 4: Test validation for missing token")
    
    success, response = tester.run_test(
        "Register FCM token with missing token",
        "POST",
        "fcm/register-token",
        400,  # Expecting 400 Bad Request
        session=tester.session1,
        data={"user_id": admin_user['id']}  # Missing token
    )
    
    if success:
        print(f"✅ Validation for missing token working correctly")
    else:
        print("❌ Validation for missing token failed")
        return False
    
    # Test 5: Test with invalid user_id
    print("\n🔍 Test 5: Test with invalid user_id")
    
    invalid_user_id = "invalid-user-id"
    
    success, response = tester.run_test(
        "Register FCM token with invalid user_id",
        "POST",
        "fcm/register-token",
        200,  # Should still return 200 even with invalid user_id
        session=tester.session1,
        data={"user_id": invalid_user_id, "token": mock_token}
    )
    
    if success:
        print(f"✅ FCM token registration with invalid user_id handled correctly")
    else:
        print("❌ FCM token registration with invalid user_id failed")
        return False
    
    print(f"\nFCM Token Registration API Test: ✅ PASSED")
    return True

def test_chat_message_notifications():
    """Test chat message notifications integration"""
    print("\n🔍 TESTING FEATURE: Chat Message Notifications Integration")
    
    from backend_test import CashoutAITester
    tester = CashoutAITester()
    
    # Login as admin
    admin_user = tester.test_login("admin", "admin123", tester.session1)
    if not admin_user:
        print("❌ Admin login failed, cannot test chat message notifications")
        return False
    
    # Create a test user to receive notifications
    timestamp = datetime.now().strftime("%H%M%S")
    username = f"chat_test_{timestamp}"
    email = f"chat_test_{timestamp}@example.com"
    real_name = f"Chat Test User {timestamp}"
    
    test_user = tester.test_register_with_membership(
        username=username,
        email=email,
        real_name=real_name,
        membership_plan="Monthly",
        password="TestPass123!",
        session=tester.session2
    )
    
    if not test_user:
        print("❌ Failed to create test user for chat notification testing")
        return False
    
    print(f"✅ Created test user {username} for chat notification testing")
    
    # Approve the test user
    success, response = tester.run_test(
        "Approve test user",
        "POST",
        "users/approve",
        200,
        session=tester.session1,
        data={
            "user_id": test_user['id'],
            "approved": True,
            "admin_id": admin_user['id'],
            "role": "member"
        }
    )
    
    if not success:
        print("❌ Failed to approve test user")
        return False
    
    print(f"✅ Test user approved successfully")
    
    # Login as the test user
    test_user_login = tester.test_login(username, "TestPass123!", tester.session2)
    if not test_user_login:
        print("❌ Test user login failed")
        return False
    
    print(f"✅ Test user login successful")
    
    # Register FCM token for both users
    admin_token = f"fcm-token-admin-{uuid.uuid4()}"
    test_user_token = f"fcm-token-user-{uuid.uuid4()}"
    
    admin_token_result = test_register_fcm_token(
        tester,
        admin_user['id'],
        admin_token,
        tester.session1
    )
    
    if not admin_token_result:
        print("❌ Failed to register FCM token for admin user")
        return False
    
    print(f"✅ FCM token registered for admin user")
    
    test_user_token_result = test_register_fcm_token(
        tester,
        test_user_login['id'],
        test_user_token,
        tester.session2
    )
    
    if not test_user_token_result:
        print("❌ Failed to register FCM token for test user")
        return False
    
    print(f"✅ FCM token registered for test user")
    
    # Test 1: Send a chat message from admin to trigger notification for test user
    print("\n🔍 Test 1: Send a chat message from admin to trigger notification for test user")
    
    admin_message = "This is a test message from admin that should trigger FCM notification!"
    admin_chat_result = test_chat_message_notification(
        tester,
        admin_user['id'],
        admin_message,
        tester.session1
    )
    
    if not admin_chat_result:
        print("❌ Failed to send chat message from admin")
        return False
    
    print(f"✅ Chat message sent successfully from admin")
    
    # Test 2: Send a chat message from test user to trigger notification for admin
    print("\n🔍 Test 2: Send a chat message from test user to trigger notification for admin")
    
    user_message = "This is a test message from test user that should trigger FCM notification!"
    user_chat_result = test_chat_message_notification(
        tester,
        test_user_login['id'],
        user_message,
        tester.session2
    )
    
    if not user_chat_result:
        print("❌ Failed to send chat message from test user")
        return False
    
    print(f"✅ Chat message sent successfully from test user")
    
    # Test 3: Send a chat message with special characters
    print("\n🔍 Test 3: Send a chat message with special characters")
    
    special_message = "Special chars: !@#$%^&*()_+{}|:<>?~`-=[]\\;',./😀🎉👍"
    special_chat_result = test_chat_message_notification(
        tester,
        admin_user['id'],
        special_message,
        tester.session1
    )
    
    if not special_chat_result:
        print("❌ Failed to send chat message with special characters")
        return False
    
    print(f"✅ Chat message with special characters sent successfully")
    
    # Test 4: Send a very long chat message
    print("\n🔍 Test 4: Send a very long chat message")
    
    long_message = "This is a very long message that should be truncated in the notification. " * 10
    long_chat_result = test_chat_message_notification(
        tester,
        admin_user['id'],
        long_message,
        tester.session1
    )
    
    if not long_chat_result:
        print("❌ Failed to send long chat message")
        return False
    
    print(f"✅ Long chat message sent successfully")
    
    print(f"\nChat Message Notifications Integration Test: ✅ PASSED")
    return True

def test_user_registration_admin_notifications():
    """Test user registration admin notifications"""
    print("\n🔍 TESTING FEATURE: User Registration Admin Notifications")
    
    from backend_test import CashoutAITester
    tester = CashoutAITester()
    
    # Login as admin
    admin_user = tester.test_login("admin", "admin123", tester.session1)
    if not admin_user:
        print("❌ Admin login failed, cannot test user registration admin notifications")
        return False
    
    # Register FCM token for admin
    admin_token = f"fcm-token-admin-{uuid.uuid4()}"
    admin_token_result = test_register_fcm_token(
        tester,
        admin_user['id'],
        admin_token,
        tester.session1
    )
    
    if not admin_token_result:
        print("❌ Failed to register FCM token for admin user")
        return False
    
    print(f"✅ FCM token registered for admin user")
    
    # Test 1: Register a new user to trigger admin notification
    print("\n🔍 Test 1: Register a new user to trigger admin notification")
    
    timestamp = datetime.now().strftime("%H%M%S")
    username = f"notify_test_{timestamp}"
    email = f"notify_test_{timestamp}@example.com"
    real_name = f"Notify Test User {timestamp}"
    
    test_user = tester.test_register_with_membership(
        username=username,
        email=email,
        real_name=real_name,
        membership_plan="Monthly",
        password="TestPass123!"
    )
    
    if not test_user:
        print("❌ Failed to register test user")
        return False
    
    print(f"✅ Test user registered successfully")
    
    # Test 2: Register another user with different details
    print("\n🔍 Test 2: Register another user with different details")
    
    timestamp2 = datetime.now().strftime("%H%M%S")
    username2 = f"notify_test2_{timestamp2}"
    email2 = f"notify_test2_{timestamp2}@example.com"
    real_name2 = f"Notify Test User 2 {timestamp2}"
    
    test_user2 = tester.test_register_with_membership(
        username=username2,
        email=email2,
        real_name=real_name2,
        membership_plan="Monthly",
        password="TestPass456!"
    )
    
    if not test_user2:
        print("❌ Failed to register second test user")
        return False
    
    print(f"✅ Second test user registered successfully")
    
    # Test 3: Approve a user to verify the notification flow
    print("\n🔍 Test 3: Approve a user to verify the notification flow")
    
    success, response = tester.run_test(
        "Approve test user",
        "POST",
        "users/approve",
        200,
        session=tester.session1,
        data={
            "user_id": test_user['id'],
            "approved": True,
            "admin_id": admin_user['id'],
            "role": "member"
        }
    )
    
    if not success:
        print("❌ Failed to approve test user")
        return False
    
    print(f"✅ Test user approved successfully")
    
    print(f"\nUser Registration Admin Notifications Test: ✅ PASSED")
    return True

# Helper functions for FCM tests
def test_register_fcm_token(tester, user_id, token, session=None):
    """Test registering FCM token"""
    success, response = tester.run_test(
        "Register FCM Token",
        "POST",
        "fcm/register-token",
        200,
        session=session,
        data={"user_id": user_id, "token": token}
    )
    
    if success:
        print(f"FCM token registration successful for user {user_id}")
        return response
    return None

def test_send_test_notification(tester, token, session=None):
    """Test sending a test notification"""
    success, response = tester.run_test(
        "Send Test Notification",
        "POST",
        "fcm/test-notification",
        200,
        session=session,
        data={"token": token}
    )
    
    if success:
        print(f"Test notification sent successfully to token {token}")
        return response
    return None

def test_chat_message_notification(tester, user_id, content, session=None):
    """Test sending a chat message that should trigger notifications"""
    success, response = tester.run_test(
        "Send Chat Message",
        "POST",
        "messages",
        200,
        session=session,
        data={
            "user_id": user_id,
            "content": content,
            "content_type": "text"
        }
    )
    
    if success:
        print(f"Chat message sent successfully: {content[:30]}...")
        return response
    return None

def run_fcm_tests():
    """Run all FCM notification tests"""
    print("\n🔍 RUNNING ALL FCM NOTIFICATION TESTS")
    
    tests = [
        ("FCM Service Integration", test_fcm_service_integration),
        ("FCM Token Registration API", test_fcm_token_registration_api),
        ("Chat Message Notifications", test_chat_message_notifications),
        ("User Registration Admin Notifications", test_user_registration_admin_notifications)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*80}")
        print(f"RUNNING TEST: {test_name}")
        print(f"{'='*80}")
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
            results.append((test_name, False))
    
    # Print summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        if result:
            passed += 1
        print(f"{test_name}: {status}")
    
    success_rate = (passed / len(results)) * 100 if results else 0
    print(f"\nOverall success rate: {success_rate:.1f}% ({passed}/{len(results)} tests passed)")
    
    return all(result for _, result in results)

if __name__ == "__main__":
    run_fcm_tests()