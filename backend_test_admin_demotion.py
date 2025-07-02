import requests
import json
import time
import sys
import os
from datetime import datetime

class AdminDemotionTester:
    def __init__(self, base_url=None):
        # Use localhost for testing
        if base_url is None:
            base_url = 'http://localhost:8001'
            
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_session = requests.Session()
        self.test_admin_session = requests.Session()
        
        print(f"🔗 Using API URL: {self.api_url}")
        
    def run_test(self, name, method, endpoint, expected_status, session=None, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        req_session = session if session else requests.Session()
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"URL: {url}")
        if data:
            print(f"Data: {json.dumps(data, indent=2)}")
        
        try:
            if method == 'GET':
                response = req_session.get(url, headers=headers)
            elif method == 'POST':
                response = req_session.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = req_session.put(url, json=data, headers=headers)
            
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
    
    def login(self, username, password, session=None):
        """Login and get user data"""
        success, response = self.run_test(
            f"Login as {username}",
            "POST",
            "users/login",
            200,
            session=session,
            data={"username": username, "password": password}
        )
        
        if success:
            print(f"Login successful for {username}")
            print(f"User ID: {response.get('id')}")
            print(f"Is Admin: {response.get('is_admin')}")
            print(f"Role: {response.get('role')}")
            return response
        return None
    
    def register_user(self, username, email, real_name, membership_plan, password, session=None):
        """Register a new user"""
        success, response = self.run_test(
            f"Register user {username}",
            "POST",
            "users/register",
            200,
            session=session,
            data={
                "username": username,
                "email": email,
                "real_name": real_name,
                "membership_plan": membership_plan,
                "password": password
            }
        )
        
        if success:
            print(f"Registration successful for {username}")
            return response
        return None
    
    def approve_user(self, admin_session, user_id, admin_id, role="member"):
        """Approve a user with specified role"""
        success, response = self.run_test(
            f"Approve user with role {role}",
            "POST",
            "users/approve",
            200,
            session=admin_session,
            data={
                "user_id": user_id,
                "approved": True,
                "admin_id": admin_id,
                "role": role
            }
        )
        
        if success:
            print(f"Successfully approved user with role {role}")
            return response
        return None
    
    def change_user_role(self, admin_session, user_id, admin_id, new_role, expected_status=200):
        """Change a user's role"""
        success, response = self.run_test(
            f"Change user role to {new_role}",
            "POST",
            "users/change-role",
            expected_status,
            session=admin_session,
            data={
                "user_id": user_id,
                "admin_id": admin_id,
                "new_role": new_role
            }
        )
        
        if success:
            print(f"Successfully changed user role to {new_role}")
            return response
        return None
    
    def get_all_users(self, session):
        """Get all approved users"""
        success, response = self.run_test(
            "Get all users",
            "GET",
            "users",
            200,
            session=session
        )
        
        if success:
            print(f"Found {len(response)} approved users")
            return response
        return None

def test_admin_demotion_comprehensive():
    """Comprehensive test for admin demotion functionality"""
    print("\n🔍 COMPREHENSIVE TESTING: Admin Demotion Functionality")
    
    tester = AdminDemotionTester()
    
    # Step 1: Login as admin
    print("\n🔍 STEP 1: Login as admin (admin/admin123)")
    admin_user = tester.login("admin", "admin123", tester.admin_session)
    if not admin_user:
        print("❌ Admin login failed, cannot test admin demotion")
        return False
    
    print("✅ Admin login successful")
    
    # Step 2: Create a test user to promote to admin
    print("\n🔍 STEP 2: Create a test user and promote to admin")
    timestamp = datetime.now().strftime("%H%M%S")
    username = f"test_admin_{timestamp}"
    email = f"test_admin_{timestamp}@example.com"
    real_name = f"Test Admin User {timestamp}"
    
    test_user = tester.register_user(
        username=username,
        email=email,
        real_name=real_name,
        membership_plan="Monthly",
        password="TestPass123!",
        session=tester.admin_session
    )
    
    if not test_user:
        print("❌ Failed to create test user")
        return False
    
    print(f"✅ Created test user {username}")
    
    # Approve the user with admin role
    approve_result = tester.approve_user(
        tester.admin_session, 
        test_user['id'], 
        admin_user['id'], 
        role="admin"
    )
    
    if not approve_result:
        print("❌ Failed to approve user as admin")
        return False
    
    print("✅ User approved as admin successfully")
    
    # Verify the user has admin role
    all_users = tester.get_all_users(tester.admin_session)
    if not all_users:
        print("❌ Failed to get all users")
        return False
    
    test_user_updated = next((user for user in all_users if user['id'] == test_user['id']), None)
    if not test_user_updated:
        print("❌ Test user not found in all users list")
        return False
    
    if test_user_updated.get('role') != "admin" or not test_user_updated.get('is_admin'):
        print(f"❌ User was not properly set as admin. Role: {test_user_updated.get('role')}, is_admin: {test_user_updated.get('is_admin')}")
        return False
    
    print(f"✅ User successfully set as admin. Role: {test_user_updated.get('role')}, is_admin: {test_user_updated.get('is_admin')}")
    
    # Step 3: Test admin demotion to member
    print("\n🔍 STEP 3: Test demoting admin to member")
    member_demotion_result = tester.change_user_role(
        tester.admin_session,
        test_user['id'],
        admin_user['id'],
        "member"
    )
    
    if not member_demotion_result:
        print("❌ Failed to demote admin to member")
        return False
    
    print("✅ Successfully demoted admin to member")
    
    # Verify the role change to member
    all_users = tester.get_all_users(tester.admin_session)
    if not all_users:
        print("❌ Failed to get all users after role change")
        return False
    
    test_user_updated = next((user for user in all_users if user['id'] == test_user['id']), None)
    if not test_user_updated:
        print("❌ Test user not found in all users list after role change")
        return False
    
    if test_user_updated.get('role') != "member":
        print(f"❌ User role was not changed to member. Current role: {test_user_updated.get('role')}")
        return False
    
    if test_user_updated.get('is_admin'):
        print("❌ is_admin flag incorrectly set to true for member role")
        return False
    
    print(f"✅ User successfully demoted to member. Role: {test_user_updated.get('role')}, is_admin: {test_user_updated.get('is_admin')}")
    
    # Step 4: Promote back to admin for next tests
    print("\n🔍 STEP 4: Promote user back to admin for next tests")
    admin_promotion_result = tester.change_user_role(
        tester.admin_session,
        test_user['id'],
        admin_user['id'],
        "admin"
    )
    
    if not admin_promotion_result:
        print("❌ Failed to promote user back to admin")
        return False
    
    print("✅ Successfully promoted user back to admin")
    
    # Verify the promotion
    all_users = tester.get_all_users(tester.admin_session)
    test_user_updated = next((user for user in all_users if user['id'] == test_user['id']), None)
    
    if test_user_updated.get('role') != "admin" or not test_user_updated.get('is_admin'):
        print(f"❌ User was not properly promoted to admin. Role: {test_user_updated.get('role')}, is_admin: {test_user_updated.get('is_admin')}")
        return False
    
    print(f"✅ User successfully promoted to admin. Role: {test_user_updated.get('role')}, is_admin: {test_user_updated.get('is_admin')}")
    
    # Step 5: Test admin demotion to moderator
    print("\n🔍 STEP 5: Test demoting admin to moderator")
    moderator_demotion_result = tester.change_user_role(
        tester.admin_session,
        test_user['id'],
        admin_user['id'],
        "moderator"
    )
    
    if not moderator_demotion_result:
        print("❌ Failed to demote admin to moderator")
        return False
    
    print("✅ Successfully demoted admin to moderator")
    
    # Verify the role change to moderator
    all_users = tester.get_all_users(tester.admin_session)
    if not all_users:
        print("❌ Failed to get all users after role change")
        return False
    
    test_user_updated = next((user for user in all_users if user['id'] == test_user['id']), None)
    if not test_user_updated:
        print("❌ Test user not found in all users list after role change")
        return False
    
    if test_user_updated.get('role') != "moderator":
        print(f"❌ User role was not changed to moderator. Current role: {test_user_updated.get('role')}")
        return False
    
    if test_user_updated.get('is_admin'):
        print("❌ is_admin flag incorrectly set to true for moderator role")
        return False
    
    print(f"✅ User successfully demoted to moderator. Role: {test_user_updated.get('role')}, is_admin: {test_user_updated.get('is_admin')}")
    
    # Step 6: Test that admin cannot demote themselves
    print("\n🔍 STEP 6: Test that admin cannot demote themselves")
    self_demotion_result = tester.change_user_role(
        tester.admin_session,
        admin_user['id'],
        admin_user['id'],
        "member",
        expected_status=400  # Expecting 400 Bad Request
    )
    
    if not self_demotion_result:
        print("❌ Self-demotion prevention test failed")
        return False
    
    print("✅ Self-demotion prevention works correctly")
    
    # Step 7: Verify database persistence
    print("\n🔍 STEP 7: Verify database persistence of role changes")
    
    # Promote back to admin for persistence test
    admin_promotion_result = tester.change_user_role(
        tester.admin_session,
        test_user['id'],
        admin_user['id'],
        "admin"
    )
    
    if not admin_promotion_result:
        print("❌ Failed to promote user back to admin for persistence test")
        return False
    
    # Logout and login again to verify persistence
    tester.admin_session.close()
    tester.admin_session = requests.Session()
    
    admin_user = tester.login("admin", "admin123", tester.admin_session)
    if not admin_user:
        print("❌ Admin login failed after session reset")
        return False
    
    # Get all users again
    all_users = tester.get_all_users(tester.admin_session)
    if not all_users:
        print("❌ Failed to get all users after session reset")
        return False
    
    # Find our test user in the list
    test_user_updated = next((user for user in all_users if user['id'] == test_user['id']), None)
    if not test_user_updated:
        print("❌ Test user not found in all users list after session reset")
        return False
    
    # Verify the role persisted
    if test_user_updated.get('role') != "admin":
        print(f"❌ User role did not persist in database. Current role: {test_user_updated.get('role')}")
        return False
    
    if not test_user_updated.get('is_admin'):
        print("❌ is_admin flag did not persist in database")
        return False
    
    print(f"✅ User role and is_admin flag correctly persisted in database. Role: {test_user_updated.get('role')}, is_admin: {test_user_updated.get('is_admin')}")
    
    # Step 8: Test that other admins can demote each other
    print("\n🔍 STEP 8: Test that other admins can demote each other")
    
    # Login as the test admin
    test_admin_user = tester.login(username, "TestPass123!", tester.test_admin_session)
    if not test_admin_user:
        print("❌ Test admin login failed")
        return False
    
    if not test_admin_user.get('is_admin') or test_admin_user.get('role') != "admin":
        print(f"❌ Test user does not have admin privileges. is_admin: {test_admin_user.get('is_admin')}, role: {test_admin_user.get('role')}")
        return False
    
    print(f"✅ Test admin login successful. is_admin: {test_admin_user.get('is_admin')}, role: {test_admin_user.get('role')}")
    
    # Create another test user to be demoted by the test admin
    timestamp2 = datetime.now().strftime("%H%M%S")
    username2 = f"test_admin2_{timestamp2}"
    email2 = f"test_admin2_{timestamp2}@example.com"
    real_name2 = f"Test Admin User 2 {timestamp2}"
    
    test_user2 = tester.register_user(
        username=username2,
        email=email2,
        real_name=real_name2,
        membership_plan="Monthly",
        password="TestPass123!",
        session=tester.admin_session
    )
    
    if not test_user2:
        print("❌ Failed to create second test user")
        return False
    
    print(f"✅ Created second test user {username2}")
    
    # Approve the second user with admin role
    approve_result2 = tester.approve_user(
        tester.admin_session, 
        test_user2['id'], 
        admin_user['id'], 
        role="admin"
    )
    
    if not approve_result2:
        print("❌ Failed to approve second user as admin")
        return False
    
    print("✅ Second user approved as admin successfully")
    
    # Have the first test admin demote the second test admin
    cross_demotion_result = tester.change_user_role(
        tester.test_admin_session,
        test_user2['id'],
        test_admin_user['id'],
        "member"
    )
    
    if not cross_demotion_result:
        print("❌ Failed to have one admin demote another admin")
        return False
    
    print("✅ Successfully had one admin demote another admin")
    
    # Verify the role change
    all_users = tester.get_all_users(tester.admin_session)
    test_user2_updated = next((user for user in all_users if user['id'] == test_user2['id']), None)
    
    if test_user2_updated.get('role') != "member":
        print(f"❌ Second user role was not changed to member. Current role: {test_user2_updated.get('role')}")
        return False
    
    if test_user2_updated.get('is_admin'):
        print("❌ is_admin flag incorrectly set to true for member role")
        return False
    
    print(f"✅ Second user successfully demoted to member by first test admin. Role: {test_user2_updated.get('role')}, is_admin: {test_user2_updated.get('is_admin')}")
    
    # Clean up - demote all test users back to member
    print("\n🔍 Cleaning up - demoting all test users back to member")
    
    tester.change_user_role(
        tester.admin_session,
        test_user['id'],
        admin_user['id'],
        "member"
    )
    
    # Summary
    print("\n✅ Admin Demotion Functionality comprehensive test passed")
    print(f"Tests run: {tester.tests_run}, Tests passed: {tester.tests_passed}")
    
    return True

if __name__ == "__main__":
    test_result = test_admin_demotion_comprehensive()
    sys.exit(0 if test_result else 1)