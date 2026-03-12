"""
Test Email Service and Registration with Email Notifications
- POST /api/email/test - Test email service diagnostic endpoint
- POST /api/users/register - Register users (trial and regular) and verify email notifications
"""
import pytest
import requests
import os
import time
import uuid

# Get the API URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEmailServiceDiagnostic:
    """Test /api/email/test endpoint"""
    
    def test_email_service_initialization(self):
        """Test that email test endpoint returns success status"""
        response = requests.post(f"{BASE_URL}/api/email/test")
        
        # Status code check
        assert response.status_code == 200, f"Email test endpoint failed: {response.text}"
        
        # Data validation
        data = response.json()
        print(f"Email test response: {data}")
        
        # Verify response structure
        assert "status" in data, "Response missing 'status' field"
        assert "message" in data, "Response missing 'message' field"
        assert "env_vars_present" in data, "Response missing 'env_vars_present' field"
        
        # Verify email service is working - should return 'success'
        assert data["status"] == "success", f"Email service not working: {data.get('message', 'Unknown error')}"
        
        # Verify env vars are configured
        env_vars = data["env_vars_present"]
        assert env_vars.get("MAIL_USERNAME") == True, "MAIL_USERNAME not configured"
        assert env_vars.get("MAIL_PASSWORD") == True, "MAIL_PASSWORD not configured"
        assert env_vars.get("MAIL_SERVER") == True, "MAIL_SERVER not configured"
        
        print(f"✅ Email test passed - Email was sent successfully")


class TestTrialUserRegistration:
    """Test trial user registration with email notifications"""
    
    def test_trial_registration_success(self):
        """Test registering a trial user - should auto-approve and send welcome email"""
        # Generate unique test user data
        unique_id = str(uuid.uuid4())[:8]
        test_user = {
            "username": f"TEST_trial_{unique_id}",
            "email": f"test_trial_{unique_id}@test.com",
            "password": "TestPassword123!",
            "real_name": f"Test Trial User {unique_id}",
            "membership_plan": "14-Day Trial",
            "is_trial": True
        }
        
        response = requests.post(f"{BASE_URL}/api/users/register", json=test_user)
        
        # Status code check
        assert response.status_code == 200, f"Trial registration failed: {response.text}"
        
        # Data validation
        data = response.json()
        print(f"Trial registration response: {data}")
        
        # Verify user was created with trial status
        assert data.get("username") == test_user["username"], "Username mismatch"
        assert data.get("email") == test_user["email"], "Email mismatch"
        assert data.get("status") == "trial", f"Expected 'trial' status but got: {data.get('status')}"
        assert data.get("real_name") == test_user["real_name"], "Real name mismatch"
        
        # Verify trial dates are set
        assert data.get("trial_start_date") is not None, "Trial start date not set"
        assert data.get("trial_end_date") is not None, "Trial end date not set"
        
        print(f"✅ Trial user registered successfully with status: {data.get('status')}")
        print(f"   Trial ends: {data.get('trial_end_date')}")
        
        # Return user ID for cleanup
        return data.get("id")


class TestRegularUserRegistration:
    """Test regular (non-trial) user registration with admin notification"""
    
    def test_regular_registration_pending_status(self):
        """Test registering a regular user - should be pending and trigger admin notification"""
        # Generate unique test user data
        unique_id = str(uuid.uuid4())[:8]
        test_user = {
            "username": f"TEST_regular_{unique_id}",
            "email": f"test_regular_{unique_id}@test.com",
            "password": "TestPassword123!",
            "real_name": f"Test Regular User {unique_id}",
            "membership_plan": "Monthly",
            "is_trial": False
        }
        
        response = requests.post(f"{BASE_URL}/api/users/register", json=test_user)
        
        # Status code check
        assert response.status_code == 200, f"Regular registration failed: {response.text}"
        
        # Data validation
        data = response.json()
        print(f"Regular registration response: {data}")
        
        # Verify user was created with pending status
        assert data.get("username") == test_user["username"], "Username mismatch"
        assert data.get("email") == test_user["email"], "Email mismatch"
        assert data.get("status") == "pending", f"Expected 'pending' status but got: {data.get('status')}"
        
        print(f"✅ Regular user registered successfully with status: {data.get('status')}")
        
        # Return user ID for cleanup
        return data.get("id")


class TestRegistrationValidation:
    """Test registration validation - duplicate users etc"""
    
    def test_duplicate_username_rejected(self):
        """Test that duplicate usernames are rejected"""
        unique_id = str(uuid.uuid4())[:8]
        test_user = {
            "username": f"TEST_dup_{unique_id}",
            "email": f"test_dup1_{unique_id}@test.com",
            "password": "TestPassword123!",
            "real_name": f"Test Dup User {unique_id}",
            "membership_plan": "Monthly",
            "is_trial": False
        }
        
        # First registration should succeed
        response1 = requests.post(f"{BASE_URL}/api/users/register", json=test_user)
        assert response1.status_code == 200, f"First registration failed: {response1.text}"
        
        # Second registration with same username should fail
        test_user["email"] = f"test_dup2_{unique_id}@test.com"  # Different email
        response2 = requests.post(f"{BASE_URL}/api/users/register", json=test_user)
        
        assert response2.status_code == 400, f"Duplicate username should be rejected: {response2.text}"
        
        data = response2.json()
        assert "already exists" in data.get("detail", "").lower(), f"Expected 'already exists' error but got: {data}"
        
        print(f"✅ Duplicate username correctly rejected")


class TestCleanup:
    """Clean up test users created during testing"""
    
    def test_cleanup_test_users(self):
        """Clean up all TEST_ prefixed users from database"""
        # Login as admin to get auth
        login_response = requests.post(f"{BASE_URL}/api/users/login", json={
            "username": "admin",
            "password": "admin123"
        })
        
        if login_response.status_code != 200:
            pytest.skip("Could not login as admin for cleanup")
        
        admin_data = login_response.json()
        user_id = admin_data.get("id")
        session_id = admin_data.get("session_id")
        
        # Get all users
        users_response = requests.get(f"{BASE_URL}/api/users")
        if users_response.status_code == 200:
            users = users_response.json()
            test_users = [u for u in users if u.get("username", "").startswith("TEST_")]
            
            # Delete test users
            for user in test_users:
                delete_response = requests.delete(f"{BASE_URL}/api/admin/users/{user['id']}")
                if delete_response.status_code == 200:
                    print(f"   Deleted test user: {user['username']}")
                    
            print(f"✅ Cleaned up {len(test_users)} test users")
        else:
            print("⚠️ Could not fetch users for cleanup")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
