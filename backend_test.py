
import requests
import json
import time
import sys
import os
from datetime import datetime

class CashoutAITester:
    def __init__(self, base_url="https://cashoutai.onrender.com"):
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
    
    def test_register_with_membership(self, username, email, real_name, membership_plan, password, session=None):
        """Test user registration with membership plan"""
        test_name = f"Register user with {membership_plan} membership plan"
        success, response = self.run_test(
            test_name,
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
            print(f"Registration successful for {username} with {membership_plan} plan")
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
    
    def test_get_stock_price(self, symbol, session=None):
        """Test real-time stock price API"""
        success, response = self.run_test(
            f"Get stock price for {symbol}",
            "GET",
            f"stock-price/{symbol}",
            200,
            session=session
        )
        
        if success:
            print(f"Current price for {symbol}: ${response.get('price')}")
            print(f"Change: {response.get('change')} ({response.get('change_percent')})")
            return response
        return None
    
    def test_get_pending_users(self, admin_session):
        """Test getting pending users as admin"""
        success, response = self.run_test(
            "Get pending users",
            "GET",
            "users/pending",
            200,
            session=admin_session
        )
        
        if success:
            print(f"Found {len(response)} pending users")
            # Check if membership plan is included in response
            if response and len(response) > 0:
                for user in response:
                    if 'membership_plan' in user:
                        print(f"User {user.get('username')} has {user.get('membership_plan')} membership plan")
                    else:
                        print(f"❌ Membership plan not found for user {user.get('username')}")
            return response
        return None
    
    def test_get_messages(self, limit=50, session=None):
        """Test getting chat messages"""
        success, response = self.run_test(
            "Get chat messages",
            "GET",
            f"messages?limit={limit}",
            200,
            session=session
        )
        
        if success:
            print(f"Retrieved {len(response)} messages")
            # Check message format
            if response and len(response) > 0:
                message = response[0]
                print(f"Message format: {message.get('username')}: {message.get('content')}")
                print(f"Timestamp: {message.get('timestamp')}")
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
    
    def test_registration_with_membership_plans(self):
        """Test registration with different membership plans"""
        print("\n📝 Testing Registration with Membership Plans...")
        
        # Test with different membership plans
        plans = ["Basic", "Premium", "Pro"]
        results = []
        
        for i, plan in enumerate(plans):
            timestamp = datetime.now().strftime("%H%M%S")
            username = f"test_user_{timestamp}_{i}"
            email = f"test_{timestamp}_{i}@example.com"
            real_name = f"Test User {i}"
            
            result = self.test_register_with_membership(
                username=username,
                email=email,
                real_name=real_name,
                membership_plan=plan,
                password="TestPass123!"
            )
            
            results.append(result is not None)
        
        success_rate = sum(results) / len(results) if results else 0
        print(f"Registration tests completed with {success_rate * 100}% success rate")
        return all(results)
    
    def test_real_time_stock_prices(self):
        """Test real-time stock price API for multiple symbols"""
        print("\n📈 Testing Real-Time Stock Prices...")
        
        symbols = ["TSLA", "AAPL", "MSFT"]
        results = []
        
        for symbol in symbols:
            result = self.test_get_stock_price(symbol)
            results.append(result is not None and 'price' in result)
            
            # Wait a bit between requests
            time.sleep(1)
        
        success_rate = sum(results) / len(results) if results else 0
        print(f"Stock price tests completed with {success_rate * 100}% success rate")
        return all(results)
    
    def test_admin_panel(self):
        """Test admin panel functionality"""
        print("\n⚙️ Testing Admin Panel...")
        
        # Login as admin
        admin_user = self.test_login("admin", "admin", self.session1)
        if not admin_user:
            print("❌ Admin login failed, cannot test admin panel")
            return False
        
        # Check if user is admin
        if not admin_user.get('is_admin'):
            print("❌ User is not an admin, cannot test admin panel")
            return False
        
        # Get pending users
        pending_users = self.test_get_pending_users(self.session1)
        if pending_users is None:
            print("❌ Failed to get pending users")
            return False
        
        return True
    
    def test_chat_message_format(self):
        """Test chat message format"""
        print("\n💬 Testing Chat Message Format...")
        
        # Get messages
        messages = self.test_get_messages(session=self.session1)
        if messages is None:
            print("❌ Failed to get messages")
            return False
        
        # Check if there are any messages
        if not messages:
            print("⚠️ No messages found to test format")
            return True  # Not a failure, just no messages to test
        
        # Check message format
        for message in messages[:5]:  # Check first 5 messages
            if 'username' not in message or 'content' not in message or 'timestamp' not in message:
                print(f"❌ Message missing required fields: {message}")
                return False
            
            # Check timestamp format
            try:
                timestamp = datetime.fromisoformat(message['timestamp'].replace('Z', '+00:00'))
                print(f"✅ Message has valid timestamp: {timestamp.strftime('%H:%M')}")
            except (ValueError, TypeError):
                print(f"❌ Invalid timestamp format: {message.get('timestamp')}")
                return False
        
        return True

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
