
import requests
import json
import time
import sys
from datetime import datetime

class CashoutAITester:
    def __init__(self, base_url="https://1494341d-df84-483f-b635-19d168bdc5cc.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.session1 = requests.Session()
        self.session2 = requests.Session()
        
    def run_test(self, name, method, endpoint, expected_status, session=None, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        req_session = session if session else requests.Session()
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = req_session.get(url, headers=headers)
            elif method == 'POST':
                response = req_session.post(url, json=data, headers=headers)
            
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
            "Login",
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
    
    def test_session_status(self, user_id, session_id, session=None):
        """Test session status endpoint"""
        success, response = self.run_test(
            "Session Status Check",
            "GET",
            f"users/{user_id}/session-status?session_id={session_id}",
            200,
            session=session
        )
        
        if success:
            print(f"Session status: {response.get('valid')}")
            print(f"Message: {response.get('message')}")
            return response
        return None
    
    def test_single_session_auth(self):
        """Test single-session authentication by logging in from two different sessions"""
        print("\n🔒 Testing Single-Session Authentication...")
        
        # First login with session 1
        user1 = self.test_login("admin", "admin", self.session1)
        if not user1:
            print("❌ First login failed, cannot continue test")
            return False
        
        user_id = user1.get('id')
        session_id1 = user1.get('active_session_id')
        
        # Check if session 1 is valid
        session1_status = self.test_session_status(user_id, session_id1, self.session1)
        if not session1_status or not session1_status.get('valid'):
            print("❌ First session is not valid, cannot continue test")
            return False
        
        print("\n⏳ Waiting 2 seconds before second login...")
        time.sleep(2)
        
        # Second login with session 2 (should invalidate session 1)
        user2 = self.test_login("admin", "admin", self.session2)
        if not user2:
            print("❌ Second login failed, cannot continue test")
            return False
        
        session_id2 = user2.get('active_session_id')
        
        # Check if session 2 is valid
        session2_status = self.test_session_status(user_id, session_id2, self.session2)
        if not session2_status or not session2_status.get('valid'):
            print("❌ Second session is not valid, test failed")
            return False
        
        print("\n⏳ Waiting 2 seconds before checking if first session was invalidated...")
        time.sleep(2)
        
        # Check if session 1 is now invalid
        session1_status_after = self.test_session_status(user_id, session_id1, self.session1)
        
        if session1_status_after and not session1_status_after.get('valid'):
            print("✅ First session was correctly invalidated after second login")
            return True
        else:
            print("❌ First session is still valid, single-session auth failed")
            return False
    
    def test_widget_page_access(self):
        """Test access to the widget page"""
        print("\n🌐 Testing Widget Page Access...")
        
        widget_url = f"{self.base_url}/cashoutai-button-widget.html"
        try:
            response = requests.get(widget_url)
            if response.status_code == 200:
                print(f"✅ Widget page accessible at {widget_url}")
                return True
            else:
                print(f"❌ Widget page not accessible, status code: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error accessing widget page: {str(e)}")
            return False

def main():
    # Get the backend URL from environment or use default
    backend_url = "https://1494341d-df84-483f-b635-19d168bdc5cc.preview.emergentagent.com"
    
    print(f"🚀 Starting CashoutAI Backend Tests against {backend_url}")
    tester = CashoutAITester(backend_url)
    
    # Test widget page access
    widget_test_result = tester.test_widget_page_access()
    
    # Test single-session authentication
    single_session_test_result = tester.test_single_session_auth()
    
    # Print summary
    print("\n📊 Test Summary:")
    print(f"Widget Page Access: {'✅ PASSED' if widget_test_result else '❌ FAILED'}")
    print(f"Single-Session Auth: {'✅ PASSED' if single_session_test_result else '❌ FAILED'}")
    print(f"Tests Passed: {tester.tests_passed}/{tester.tests_run}")
    
    # Return success if all tests passed
    return 0 if widget_test_result and single_session_test_result else 1

if __name__ == "__main__":
    sys.exit(main())
