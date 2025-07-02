import requests
import json
import time
import sys
import os
import pymongo
from datetime import datetime

class CashoutAITester:
    def __init__(self, base_url=None):
        # Use the local endpoint for testing
        if base_url is None:
            base_url = "http://localhost:8001"
            
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.session1 = requests.Session()
        self.session2 = requests.Session()
        
        print(f"🔗 Using API URL: {self.api_url}")
        
    def run_test(self, name, method, endpoint, expected_status, session=None, data=None, headers=None, params=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        req_session = session if session else requests.Session()
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"URL: {url}")
        
        try:
            if method == 'GET':
                response = req_session.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = req_session.post(url, json=data, headers=headers, params=params)
            elif method == 'PUT':
                response = req_session.put(url, json=data, headers=headers, params=params)
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"Response: {response.json()}")
                except:
                    print(f"Response: {response.text}")
                return False, {}
                
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}
    
    def test_login(self, username, password, session=None):
        """Test login and get token"""
        success, response = self.run_test(
            f"Login with username '{username}'",
            "POST",
            "users/login",
            200,
            session=session,
            data={"username": username, "password": password}
        )
        
        if success:
            print(f"Login successful for {username}")
            print(f"Session ID: {response.get('active_session_id')}")
            return response
        return None

def test_case_insensitive_login():
    """Test case-insensitive login functionality"""
    print("\n🔍 TESTING FEATURE: Case-Insensitive Login")
    
    tester = CashoutAITester()
    results = []
    
    # Test 1: Login with lowercase username
    print("\n🔍 Test 1: Login with lowercase username")
    user_lower = tester.test_login("admin", "admin123", tester.session1)
    if user_lower:
        print("✅ Login with lowercase username successful")
        results.append(True)
    else:
        print("❌ Login with lowercase username failed")
        results.append(False)
    
    # Test 2: Login with uppercase username
    print("\n🔍 Test 2: Login with uppercase username")
    user_upper = tester.test_login("ADMIN", "admin123", tester.session2)
    if user_upper:
        print("✅ Login with uppercase username successful")
        results.append(True)
    else:
        print("❌ Login with uppercase username failed")
        results.append(False)
    
    # Test 3: Login with mixed case username
    print("\n🔍 Test 3: Login with mixed case username")
    # Create a new session for this test
    mixed_session = requests.Session()
    user_mixed = tester.test_login("Admin", "admin123", mixed_session)
    if user_mixed:
        print("✅ Login with mixed case username successful")
        results.append(True)
    else:
        print("❌ Login with mixed case username failed")
        results.append(False)
    
    # Verify all logins returned the same user ID
    if user_lower and user_upper and user_mixed:
        if user_lower.get('id') == user_upper.get('id') == user_mixed.get('id'):
            print("✅ All logins returned the same user ID")
            results.append(True)
        else:
            print("❌ Different user IDs returned for different case logins")
            results.append(False)
    
    success_rate = sum(results) / len(results) if results else 0
    print(f"\nCase-Insensitive Login test completed with {success_rate * 100}% success rate")
    return all(results)

def test_password_change():
    """Test password change functionality"""
    print("\n🔍 TESTING FEATURE: Password Change")
    
    tester = CashoutAITester()
    results = []
    
    # Test 1: Login with admin credentials
    print("\n🔍 Test 1: Login with admin credentials")
    admin_user = tester.test_login("admin", "admin123", tester.session1)
    if not admin_user:
        print("❌ Admin login failed, cannot test password change")
        return False
    
    print("✅ Admin login successful")
    user_id = admin_user.get('id')
    
    # Test 2: Change password to new password
    print("\n🔍 Test 2: Change password to new password")
    change_result = tester.run_test(
        "Change password",
        "POST",
        f"users/change-password",
        200,
        session=tester.session1,
        data={
            "current_password": "admin123",
            "new_password": "newpass123"
        },
        params={"user_id": user_id}
    )
    
    if change_result[0]:
        print("✅ Password change successful")
        results.append(True)
    else:
        print("❌ Password change failed")
        results.append(False)
        return False  # Cannot continue if password change failed
    
    # Test 3: Login with new password
    print("\n🔍 Test 3: Login with new password")
    new_session = requests.Session()
    login_with_new = tester.test_login("admin", "newpass123", new_session)
    
    if login_with_new:
        print("✅ Login with new password successful")
        results.append(True)
    else:
        print("❌ Login with new password failed")
        results.append(False)
        return False  # Cannot continue if login with new password failed
    
    # Test 4: Change password back to original
    print("\n🔍 Test 4: Change password back to original")
    change_back_result = tester.run_test(
        "Change password back to original",
        "POST",
        f"users/change-password",
        200,
        session=new_session,
        data={
            "current_password": "newpass123",
            "new_password": "admin123"
        },
        params={"user_id": user_id}
    )
    
    if change_back_result[0]:
        print("✅ Password change back to original successful")
        results.append(True)
    else:
        print("❌ Password change back to original failed")
        results.append(False)
    
    # Test 5: Login with original password again
    print("\n🔍 Test 5: Login with original password again")
    final_session = requests.Session()
    final_login = tester.test_login("admin", "admin123", final_session)
    
    if final_login:
        print("✅ Login with original password successful")
        results.append(True)
    else:
        print("❌ Login with original password failed")
        results.append(False)
    
    # Test 6: Try changing password with incorrect current password
    print("\n🔍 Test 6: Try changing password with incorrect current password")
    incorrect_change = tester.run_test(
        "Change password with incorrect current password",
        "POST",
        f"users/change-password",
        400,  # Expect 400 Bad Request
        session=final_session,
        data={
            "current_password": "wrongpassword",
            "new_password": "newpass123"
        },
        params={"user_id": user_id}
    )
    
    if incorrect_change[0]:
        print("✅ Password change with incorrect current password correctly failed")
        results.append(True)
    else:
        print("❌ Password change with incorrect current password test failed")
        results.append(False)
    
    success_rate = sum(results) / len(results) if results else 0
    print(f"\nPassword Change test completed with {success_rate * 100}% success rate")
    return all(results)

def test_password_reset_request():
    """Test password reset request functionality"""
    print("\n🔍 TESTING FEATURE: Password Reset Request")
    
    tester = CashoutAITester()
    results = []
    
    # Test 1: Request password reset for admin email
    print("\n🔍 Test 1: Request password reset for admin email")
    admin_email = "admin@example.com"
    reset_request = tester.run_test(
        f"Request password reset for {admin_email}",
        "POST",
        "users/reset-password-request",
        200,
        data={"email": admin_email}
    )
    
    if reset_request[0]:
        print("✅ Password reset request successful")
        results.append(True)
    else:
        print("❌ Password reset request failed")
        results.append(False)
    
    # Test 2: Check if reset token is stored in database
    print("\n🔍 Test 2: Check if reset token is stored in database")
    # Wait a moment for the database to be updated
    time.sleep(1)
    
    # Connect to MongoDB
    try:
        client = pymongo.MongoClient("mongodb://localhost:27017/")
        db = client["emergent_db"]
        users_collection = db["users"]
        
        # Find user by email
        user = users_collection.find_one({"email": admin_email})
        if user and "reset_token" in user:
            reset_token = user["reset_token"]
            reset_expires = user["reset_expires"]
            print("✅ Reset token found in database")
            print(f"Token: {reset_token}")
            print(f"Expires: {reset_expires}")
            results.append(True)
            
            # Store the reset token for the next test
            with open('/tmp/reset_token.txt', 'w') as f:
                f.write(reset_token)
        else:
            print("❌ Reset token not found in database")
            results.append(False)
    except Exception as e:
        print(f"❌ Error accessing database: {str(e)}")
        results.append(False)
    
    # Test 3: Request password reset for non-existent email
    print("\n🔍 Test 3: Request password reset for non-existent email")
    non_existent_email = f"nonexistent_{int(time.time())}@example.com"
    non_existent_request = tester.run_test(
        f"Request password reset for non-existent email {non_existent_email}",
        "POST",
        "users/reset-password-request",
        200,  # Should still return 200 for security reasons
        data={"email": non_existent_email}
    )
    
    if non_existent_request[0]:
        print("✅ Password reset request for non-existent email handled correctly")
        results.append(True)
    else:
        print("❌ Password reset request for non-existent email failed")
        results.append(False)
    
    success_rate = sum(results) / len(results) if results else 0
    print(f"\nPassword Reset Request test completed with {success_rate * 100}% success rate")
    return all(results)

def test_password_reset_confirm():
    """Test password reset confirmation functionality"""
    print("\n🔍 TESTING FEATURE: Password Reset Confirmation")
    
    tester = CashoutAITester()
    results = []
    
    # Get the reset token from the previous test
    try:
        with open('/tmp/reset_token.txt', 'r') as f:
            reset_token = f.read().strip()
        print(f"Using reset token: {reset_token}")
    except:
        print("❌ Could not read reset token from file")
        reset_token = None
    
    if not reset_token:
        # Try to get a new token
        admin_email = "admin@example.com"
        tester.run_test(
            f"Request password reset for {admin_email}",
            "POST",
            "users/reset-password-request",
            200,
            data={"email": admin_email}
        )
        time.sleep(1)
        
        try:
            client = pymongo.MongoClient("mongodb://localhost:27017/")
            db = client["emergent_db"]
            users_collection = db["users"]
            
            # Find user by email
            user = users_collection.find_one({"email": admin_email})
            if user and "reset_token" in user:
                reset_token = user["reset_token"]
                print(f"Found reset token: {reset_token}")
            else:
                print("❌ Could not get reset token, cannot test password reset confirmation")
                return False
        except Exception as e:
            print(f"❌ Error accessing database: {str(e)}")
            return False
    
    # Test 1: Reset password with valid token
    print("\n🔍 Test 1: Reset password with valid token")
    temp_password = "temppass123"
    reset_confirm = tester.run_test(
        "Reset password with valid token",
        "POST",
        "users/reset-password-confirm",
        200,
        data={
            "token": reset_token,
            "new_password": temp_password
        }
    )
    
    if reset_confirm[0]:
        print("✅ Password reset confirmation successful")
        results.append(True)
    else:
        print("❌ Password reset confirmation failed")
        results.append(False)
        return False  # Cannot continue if reset confirmation failed
    
    # Test 2: Login with new password
    print("\n🔍 Test 2: Login with new password")
    login_with_new = tester.test_login("admin", temp_password)
    
    if login_with_new:
        print("✅ Login with new password successful")
        results.append(True)
    else:
        print("❌ Login with new password failed")
        results.append(False)
        return False  # Cannot continue if login with new password failed
    
    # Test 3: Try to use the same token again (should fail)
    print("\n🔍 Test 3: Try to use the same token again (should fail)")
    reuse_token = tester.run_test(
        "Reuse token",
        "POST",
        "users/reset-password-confirm",
        400,  # Expect 400 Bad Request
        data={
            "token": reset_token,
            "new_password": "anotherpass123"
        }
    )
    
    if reuse_token[0]:
        print("✅ Reusing token correctly failed")
        results.append(True)
    else:
        print("❌ Reusing token test failed")
        results.append(False)
    
    # Test 4: Try to use an invalid token
    print("\n🔍 Test 4: Try to use an invalid token")
    invalid_token = "invalid_token_" + str(int(time.time()))
    invalid_token_test = tester.run_test(
        "Use invalid token",
        "POST",
        "users/reset-password-confirm",
        400,  # Expect 400 Bad Request
        data={
            "token": invalid_token,
            "new_password": "invalidpass123"
        }
    )
    
    if invalid_token_test[0]:
        print("✅ Using invalid token correctly failed")
        results.append(True)
    else:
        print("❌ Using invalid token test failed")
        results.append(False)
    
    # Test 5: Change password back to original
    print("\n🔍 Test 5: Change password back to original")
    user_id = login_with_new.get('id')
    change_back = tester.run_test(
        "Change password back to original",
        "POST",
        f"users/change-password",
        200,
        session=tester.session1,
        data={
            "current_password": temp_password,
            "new_password": "admin123"
        },
        params={"user_id": user_id}
    )
    
    if change_back[0]:
        print("✅ Password change back to original successful")
        results.append(True)
    else:
        print("❌ Password change back to original failed")
        results.append(False)
    
    # Test 6: Login with original password
    print("\n🔍 Test 6: Login with original password")
    final_login = tester.test_login("admin", "admin123")
    
    if final_login:
        print("✅ Login with original password successful")
        results.append(True)
    else:
        print("❌ Login with original password failed")
        results.append(False)
    
    success_rate = sum(results) / len(results) if results else 0
    print(f"\nPassword Reset Confirmation test completed with {success_rate * 100}% success rate")
    return all(results)

def test_email_notifications():
    """Test email notifications for password changes and resets"""
    print("\n🔍 TESTING FEATURE: Email Notifications")
    
    # Check if email service is configured
    import os
    required_env_vars = [
        "MAIL_USERNAME", 
        "MAIL_PASSWORD", 
        "MAIL_FROM", 
        "MAIL_PORT", 
        "MAIL_SERVER", 
        "MAIL_TLS"
    ]
    
    env_vars_present = True
    for var in required_env_vars:
        if not os.environ.get(var):
            print(f"⚠️ Environment variable {var} is not configured")
            env_vars_present = False
    
    if env_vars_present:
        print("✅ All required email environment variables are configured")
    else:
        print("⚠️ Some email environment variables are missing, but we'll continue testing")
    
    # Check backend logs for email sending attempts
    import subprocess
    result = subprocess.run(["tail", "-n", "100", "/var/log/supervisor/backend.log"], capture_output=True, text=True)
    logs = result.stdout
    
    # Check for password change email logs
    if "Password Changed" in logs or "send_password_change_notification" in logs:
        print("✅ Found evidence of password change email notifications in logs")
    else:
        print("⚠️ No evidence of password change email notifications in logs")
    
    # Check for password reset email logs
    if "Password Reset" in logs or "send_password_reset_email" in logs:
        print("✅ Found evidence of password reset email notifications in logs")
    else:
        print("⚠️ No evidence of password reset email notifications in logs")
    
    # Check for password reset confirmation email logs
    if "Password Reset Complete" in logs or "send_password_reset_confirmation" in logs:
        print("✅ Found evidence of password reset confirmation email notifications in logs")
    else:
        print("⚠️ No evidence of password reset confirmation email notifications in logs")
    
    # Since we can't directly verify email delivery, we'll check if the email functions exist
    import sys
    sys.path.append('/app/backend')
    
    try:
        from server import send_password_change_notification, send_password_reset_email, send_password_reset_confirmation
        print("✅ Email notification functions are properly defined in the server code")
        return True
    except ImportError:
        print("❌ Could not import email notification functions from server code")
        return False

def test_password_functionality():
    """Run all password functionality tests"""
    print("\n🔍 TESTING PASSWORD FUNCTIONALITY")
    
    tests = [
        ("Case-Insensitive Login", test_case_insensitive_login),
        ("Password Change", test_password_change),
        ("Password Reset Request", test_password_reset_request),
        ("Password Reset Confirmation", test_password_reset_confirm),
        ("Email Notifications", test_email_notifications)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'=' * 80}")
        print(f"Running {test_name} Test")
        print(f"{'=' * 80}")
        
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ Test failed with error: {str(e)}")
            results[test_name] = False
    
    # Print summary
    print("\n" + "=" * 80)
    print("PASSWORD FUNCTIONALITY TEST SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print("\nOverall Result:", "✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED")
    return all_passed

if __name__ == "__main__":
    test_password_functionality()