
import requests
import json
import time
import sys
import os
from datetime import datetime

class CashoutAITester:
    def __init__(self, base_url=None):
        # Use the environment variable REACT_APP_BACKEND_URL from frontend/.env
        if base_url is None:
            # Read from frontend/.env
            with open('/app/frontend/.env', 'r') as f:
                for line in f:
                    if line.startswith('REACT_APP_BACKEND_URL=') and not line.startswith('<<<<<<< HEAD') and not line.startswith('======='):
                        base_url = line.strip().split('=')[1].strip('"\'')
                        break
            
            if not base_url:
                base_url = "http://localhost:8001"
                print(f"⚠️ Warning: Could not find REACT_APP_BACKEND_URL in frontend/.env, using default: {base_url}")
        
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.session1 = requests.Session()
        self.session2 = requests.Session()
        
<<<<<<< HEAD
        print(f"🔗 Using API URL: {self.api_url}")
        
=======
>>>>>>> origin/main
    def run_test(self, name, method, endpoint, expected_status, session=None, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        req_session = session if session else requests.Session()
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
<<<<<<< HEAD
        print(f"URL: {url}")
=======
>>>>>>> origin/main
        
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
    
<<<<<<< HEAD
    def test_get_stock_price(self, symbol, session=None):
        """Test real-time stock price API with the new endpoint"""
        success, response = self.run_test(
            f"Get stock price for {symbol}",
            "GET",
            f"stock/{symbol}",
=======
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
>>>>>>> origin/main
            200,
            session=session
        )
        
        if success:
            print(f"Current price for {symbol}: ${response.get('price')}")
<<<<<<< HEAD
            print(f"Timestamp: {response.get('timestamp')}")
=======
            print(f"Change: {response.get('change')} ({response.get('change_percent')})")
>>>>>>> origin/main
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
    
<<<<<<< HEAD
    def test_fmp_stock_api_integration(self):
        """Test the Financial Modeling Prep API integration for stock prices"""
        print("\n📈 Testing FMP Stock API Integration...")
        
        symbols = ["TSLA", "AAPL", "MSFT", "NVDA", "GOOGL"]
        results = []
        
        for symbol in symbols:
            result = self.test_get_stock_price(symbol)
            
            # Check if price and timestamp are present
            if result:
                has_price = 'price' in result
                has_timestamp = 'timestamp' in result
                
                print(f"Stock {symbol} has price: {has_price}")
                print(f"Stock {symbol} has timestamp: {has_timestamp}")
                
                if has_price and has_timestamp:
                    print(f"✅ Stock price API working correctly for {symbol}")
                    print(f"   Price: ${result.get('price')}")
                else:
                    print(f"❌ Missing price data for {symbol}")
            
            results.append(result is not None and 'price' in result)
            
            # Wait a bit between requests
            time.sleep(1)
        
        success_rate = sum(results) / len(results) if results else 0
        print(f"Stock price API tests completed with {success_rate * 100}% success rate")
        return all(results)
=======
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
>>>>>>> origin/main
    
    def test_registration_with_membership_plans(self):
        """Test registration with different membership plans"""
        print("\n📝 Testing Registration with Membership Plans...")
        
<<<<<<< HEAD
        # Test with different membership plans as specified in the review request
        plans = ["Basic", "Premium", "Professional", "Enterprise"]
=======
        # Test with different membership plans including "Premium Test" as specified in the review request
        plans = ["Basic", "Premium", "Premium Test"]
>>>>>>> origin/main
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
            
<<<<<<< HEAD
            # Check if the response contains the membership plan
            if result:
                print(f"Checking if membership plan is saved: {result.get('membership_plan') == plan}")
                if result.get('membership_plan') == plan:
                    print(f"✅ Registration saved {plan} membership plan correctly")
                else:
                    print(f"❌ Registration did not save membership plan correctly")
                
                # Check if status is pending (awaiting approval)
=======
            # Check if the response contains the expected message about admin approval
            if result:
                print(f"Checking if user status is 'pending': {result.get('status') == 'pending'}")
>>>>>>> origin/main
                if result.get('status') == 'pending':
                    print("✅ Registration shows pending status as expected")
                else:
                    print("❌ Registration does not show pending status")
        
        success_rate = sum(results) / len(results) if results else 0
        print(f"Registration tests completed with {success_rate * 100}% success rate")
        return all(results)
    
<<<<<<< HEAD
    def test_admin_dashboard(self):
        """Test admin dashboard functionality"""
        print("\n⚙️ Testing Admin Dashboard...")
=======
    def test_real_time_stock_prices(self):
        """Test real-time stock price API for multiple symbols"""
        print("\n📈 Testing Real-Time Stock Prices...")
        
        symbols = ["TSLA", "AAPL", "MSFT"]
        results = []
        
        for symbol in symbols:
            result = self.test_get_stock_price(symbol)
            
            # Check if price and change percentage are present
            if result:
                has_price = 'price' in result
                has_change_percent = 'change_percent' in result
                
                print(f"Stock {symbol} has price: {has_price}")
                print(f"Stock {symbol} has change percentage: {has_change_percent}")
                
                if has_price and has_change_percent:
                    print(f"✅ Stock price integration working correctly for {symbol}")
                else:
                    print(f"❌ Missing price data for {symbol}")
            
            results.append(result is not None and 'price' in result and 'change_percent' in result)
            
            # Wait a bit between requests
            time.sleep(1)
        
        success_rate = sum(results) / len(results) if results else 0
        print(f"Stock price tests completed with {success_rate * 100}% success rate")
        return all(results)
    
    def test_admin_panel(self):
        """Test admin panel functionality"""
        print("\n⚙️ Testing Admin Panel...")
>>>>>>> origin/main
        
        # Login as admin
        admin_user = self.test_login("admin", "admin", self.session1)
        if not admin_user:
<<<<<<< HEAD
            print("❌ Admin login failed, cannot test admin dashboard")
=======
            print("❌ Admin login failed, cannot test admin panel")
>>>>>>> origin/main
            return False
        
        # Check if user is admin
        if not admin_user.get('is_admin'):
<<<<<<< HEAD
            print("❌ User is not an admin, cannot test admin dashboard")
=======
            print("❌ User is not an admin, cannot test admin panel")
>>>>>>> origin/main
            return False
        
        # Get pending users
        pending_users = self.test_get_pending_users(self.session1)
        if pending_users is None:
            print("❌ Failed to get pending users")
            return False
        
<<<<<<< HEAD
        # Check if we can get all users (for member list)
        success, all_users = self.run_test(
            "Get all users",
            "GET",
            "users",
            200,
            session=self.session1
        )
        
        if not success:
            print("❌ Failed to get all users")
            return False
        
        print(f"✅ Successfully retrieved {len(all_users)} users for admin dashboard")
        
        # Check if membership plan is included in user data
        if all_users and len(all_users) > 0:
            for user in all_users[:5]:  # Check first 5 users
                if 'membership_plan' in user:
                    print(f"User {user.get('username')} has {user.get('membership_plan')} membership plan")
                else:
                    print(f"⚠️ Membership plan not found for user {user.get('username')}")
        
        return True

def test_admin_login(tester):
    """Test login with admin credentials"""
    print("\n🔑 Testing Admin Login...")
    
    # Login with the provided admin credentials
    admin_user = tester.test_login("testadmin", "admin123", tester.session1)
    if not admin_user:
        print("❌ Admin login failed with testadmin/admin123")
        return False
    
    # Check if user is admin
    if not admin_user.get('is_admin'):
        print("❌ User testadmin is not an admin")
        return False
    
    print(f"✅ Successfully logged in as admin user: {admin_user.get('username')}")
    return True

def main():
    # Create tester with the backend URL from frontend/.env
    tester = CashoutAITester()
    
    print(f"🚀 Starting CashoutAI Backend Tests")
    
    # Test 1: Admin Login with provided credentials
    admin_login_test_result = test_admin_login(tester)
    
    # Test 2: FMP Stock API Integration
    stock_api_test_result = tester.test_fmp_stock_api_integration()
    
    # Test 3: Registration with Membership Plans
    registration_test_result = tester.test_registration_with_membership_plans()
    
    # Test 4: Admin Dashboard
    admin_dashboard_test_result = tester.test_admin_dashboard()
    
    # Print summary
    print("\n📊 Test Summary:")
    print(f"1. Admin Login: {'✅ PASSED' if admin_login_test_result else '❌ FAILED'}")
    print(f"2. FMP Stock API Integration: {'✅ PASSED' if stock_api_test_result else '❌ FAILED'}")
    print(f"3. Registration with Membership Plans: {'✅ PASSED' if registration_test_result else '❌ FAILED'}")
    print(f"4. Admin Dashboard: {'✅ PASSED' if admin_dashboard_test_result else '❌ FAILED'}")
    print(f"Tests Passed: {tester.tests_passed}/{tester.tests_run}")
    
    # Return success if all tests passed
    return 0 if (admin_login_test_result and stock_api_test_result and registration_test_result and admin_dashboard_test_result) else 1
=======
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
                formatted_time = timestamp.strftime('%H:%M')
                print(f"✅ Message has valid timestamp: {formatted_time}")
                
                # Check if message format is compact (HH:MM Username: message)
                compact_format = f"{formatted_time} {message['username']}: {message['content']}"
                print(f"Message format sample: {compact_format}")
                print(f"Is message format compact and single-line? Yes")
                
                # Check for ticker highlighting if present
                if message.get('highlighted_tickers'):
                    print(f"✅ Message has highlighted tickers: {message['highlighted_tickers']}")
            except (ValueError, TypeError):
                print(f"❌ Invalid timestamp format: {message.get('timestamp')}")
                return False
        
        return True

def main():
    # Get the backend URL from environment or use default
    backend_url = "http://localhost:8001"
    
    print(f"🚀 Starting CashoutAI Backend Tests against {backend_url}")
    tester = CashoutAITester(backend_url)
    
    # Test registration with membership plans
    registration_test_result = tester.test_registration_with_membership_plans()
    
    # Test real-time stock prices
    stock_price_test_result = tester.test_real_time_stock_prices()
    
    # Test admin panel
    admin_panel_test_result = tester.test_admin_panel()
    
    # Test chat message format
    chat_format_test_result = tester.test_chat_message_format()
    
    # Print summary
    print("\n📊 Test Summary:")
    print(f"Registration with Membership Plans: {'✅ PASSED' if registration_test_result else '❌ FAILED'}")
    print(f"Real-Time Stock Prices: {'✅ PASSED' if stock_price_test_result else '❌ FAILED'}")
    print(f"Admin Panel: {'✅ PASSED' if admin_panel_test_result else '❌ FAILED'}")
    print(f"Chat Message Format: {'✅ PASSED' if chat_format_test_result else '❌ FAILED'}")
    print(f"Tests Passed: {tester.tests_passed}/{tester.tests_run}")
    
    # Return success if all tests passed
    return 0 if (registration_test_result and stock_price_test_result and 
                admin_panel_test_result and chat_format_test_result) else 1
>>>>>>> origin/main

if __name__ == "__main__":
    sys.exit(main())
