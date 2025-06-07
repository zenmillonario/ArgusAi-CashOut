
import requests
import json
import time
import sys
import os
from datetime import datetime

class CashoutAITester:
    def __init__(self, base_url=None):
        # Use localhost for testing
        if base_url is None:
            base_url = "http://localhost:8001"
            
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.session1 = requests.Session()
        self.session2 = requests.Session()
        
        print(f"🔗 Using API URL: {self.api_url}")
        
    def run_test(self, name, method, endpoint, expected_status, session=None, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        req_session = session if session else requests.Session()
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"URL: {url}")
        
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
    
    def test_get_stock_price(self, symbol, session=None):
        """Test real-time stock price API"""
        success, response = self.run_test(
            f"Get stock price for {symbol}",
            "GET",
            f"stock/{symbol}",
            200,
            session=session
        )
        
        if success:
            print(f"Current price for {symbol}: ${response.get('price')}")
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
    
    def test_get_all_users(self, admin_session):
        """Test getting all approved users as admin"""
        success, response = self.run_test(
            "Get all users",
            "GET",
            "users",
            200,
            session=admin_session
        )
        
        if success:
            print(f"Found {len(response)} approved users")
            return response
        return None
    
    def test_user_approval(self, admin_session, user_id, admin_id, approved=True):
        """Test approving or rejecting a user"""
        action = "approving" if approved else "rejecting"
        success, response = self.run_test(
            f"Test {action} user",
            "POST",
            "users/approve",
            200,
            session=admin_session,
            data={
                "user_id": user_id,
                "approved": approved,
                "admin_id": admin_id,
                "role": "member"
            }
        )
        
        if success:
            print(f"Successfully {action} user {user_id}")
            return response
        return None
    
    def test_user_performance(self, user_id, session=None):
        """Test getting user trading performance"""
        success, response = self.run_test(
            "Get user performance",
            "GET",
            f"users/{user_id}/performance",
            200,
            session=session
        )
        
        if success:
            print(f"User performance: {response}")
            return response
        return None
    
    def test_get_positions(self, user_id, session=None):
        """Test getting user positions"""
        success, response = self.run_test(
            "Get user positions",
            "GET",
            f"positions/{user_id}",
            200,
            session=session
        )
        
        if success:
            print(f"Found {len(response)} open positions")
            return response
        return None

def test_membership_types():
    """Test the updated membership types in registration"""
    print("\n🔍 TESTING FEATURE: Updated Membership Types")
    
    tester = CashoutAITester()
    
    # Test registration with each of the new membership types
    membership_types = ["Monthly", "Yearly", "Lifetime"]
    results = []
    
    for i, plan in enumerate(membership_types):
        timestamp = datetime.now().strftime("%H%M%S")
        username = f"test_user_{timestamp}_{i}"
        email = f"test_{timestamp}_{i}@example.com"
        real_name = f"Test User {timestamp} {i}"
        
        result = tester.test_register_with_membership(
            username=username,
            email=email,
            real_name=real_name,
            membership_plan=plan,
            password="TestPass123!"
        )
        
        if result:
            print(f"✅ Registration with {plan} membership plan successful")
            print(f"Saved membership plan: {result.get('membership_plan')}")
            if result.get('membership_plan') == plan:
                results.append(True)
            else:
                results.append(False)
                print(f"❌ Membership plan mismatch: expected {plan}, got {result.get('membership_plan')}")
        else:
            results.append(False)
            print(f"❌ Registration with {plan} membership plan failed")
    
    success_rate = sum(results) / len(results) if results else 0
    print(f"Membership types test completed with {success_rate * 100}% success rate")
    return all(results)

def test_stock_price_api():
    """Test the stock price API for practice and favorites tabs"""
    print("\n🔍 TESTING FEATURE: Stock Prices API")
    
    tester = CashoutAITester()
    
    # Test with popular stock symbols
    symbols = ["TSLA", "AAPL", "MSFT", "NVDA", "GOOGL"]
    results = []
    
    for symbol in symbols:
        result = tester.test_get_stock_price(symbol)
        
        if result and 'price' in result:
            print(f"✅ Stock price API returned price for {symbol}: ${result.get('price')}")
            results.append(True)
        else:
            print(f"❌ Stock price API failed for {symbol}")
            results.append(False)
    
    success_rate = sum(results) / len(results) if results else 0
    print(f"Stock price API test completed with {success_rate * 100}% success rate")
    return all(results)

def test_user_approval_bug_fix():
    """Test the user approval bug fix"""
    print("\n🔍 TESTING FEATURE: User Approval Bug Fix")
    
    tester = CashoutAITester()
    
    # Login as admin
    admin_user = tester.test_login("admin", "admin", tester.session1)
    if not admin_user:
        print("❌ Admin login failed, cannot test user approval bug fix")
        return False
    
    # Create a test user to approve/reject
    timestamp = datetime.now().strftime("%H%M%S")
    username = f"test_reject_{timestamp}"
    email = f"test_reject_{timestamp}@example.com"
    real_name = f"Test Reject User {timestamp}"
    
    test_user = tester.test_register_with_membership(
        username=username,
        email=email,
        real_name=real_name,
        membership_plan="Monthly",
        password="TestPass123!"
    )
    
    if not test_user:
        print("❌ Failed to create test user")
        return False
    
    # Get initial list of all users
    initial_users = tester.test_get_all_users(tester.session1)
    if initial_users is None:
        print("❌ Failed to get initial list of users")
        return False
    
    # Reject the user
    reject_result = tester.test_user_approval(
        tester.session1, 
        test_user['id'], 
        admin_user['id'], 
        approved=False
    )
    
    if not reject_result:
        print("❌ Failed to reject user")
        return False
    
    # Get updated list of all users
    updated_users = tester.test_get_all_users(tester.session1)
    if updated_users is None:
        print("❌ Failed to get updated list of users")
        return False
    
    # Check if rejected user is NOT in the list of all users
    rejected_user_found = any(user['id'] == test_user['id'] for user in updated_users)
    
    if rejected_user_found:
        print("❌ Bug still exists: Rejected user still appears in the list of all users")
        return False
    else:
        print("✅ Bug fixed: Rejected user does NOT appear in the list of all users")
        return True

def test_profile_performance_metrics():
    """Test the profile tab enhancements for trading performance"""
    print("\n🔍 TESTING FEATURE: Profile Tab Trading Performance Metrics")
    
    tester = CashoutAITester()
    
    # Login as a user
    user = tester.test_login("admin", "admin", tester.session1)
    if not user:
        print("❌ Login failed, cannot test profile performance metrics")
        return False
    
    # Get user performance metrics
    performance = tester.test_user_performance(user['id'], tester.session1)
    if not performance:
        print("❌ Failed to get user performance metrics")
        return False
    
    # Check if all required metrics are present
    required_metrics = ['total_profit', 'win_percentage', 'trades_count', 'average_gain']
    missing_metrics = [metric for metric in required_metrics if metric not in performance]
    
    if missing_metrics:
        print(f"❌ Missing performance metrics: {', '.join(missing_metrics)}")
        return False
    
    print("✅ All required performance metrics are present:")
    print(f"  - Total Trades: {performance.get('trades_count')}")
    print(f"  - Total P&L: ${performance.get('total_profit')}")
    print(f"  - Win Rate: {performance.get('win_percentage')}%")
    
    # Get open positions count
    positions = tester.test_get_positions(user['id'], tester.session1)
    if positions is None:
        print("❌ Failed to get user positions")
        return False
    
    print(f"  - Open Positions: {len(positions)}")
    
    return True

def main():
    print("🚀 Starting ArgusAI-CashOut Backend Tests")
    
    # Test 1: Updated Membership Types
    membership_test_result = test_membership_types()
    
    # Test 2: Stock Price API
    stock_price_test_result = test_stock_price_api()
    
    # Test 3: User Approval Bug Fix
    user_approval_test_result = test_user_approval_bug_fix()
    
    # Test 4: Profile Performance Metrics
    profile_metrics_test_result = test_profile_performance_metrics()
    
    # Print summary
    print("\n📊 Test Summary:")
    print(f"1. Updated Membership Types: {'✅ PASSED' if membership_test_result else '❌ FAILED'}")
    print(f"2. Stock Price API: {'✅ PASSED' if stock_price_test_result else '❌ FAILED'}")
    print(f"3. User Approval Bug Fix: {'✅ PASSED' if user_approval_test_result else '❌ FAILED'}")
    print(f"4. Profile Performance Metrics: {'✅ PASSED' if profile_metrics_test_result else '❌ FAILED'}")
    
    # Return success if all tests passed
    return 0 if (membership_test_result and stock_price_test_result and 
                user_approval_test_result and profile_metrics_test_result) else 1

if __name__ == "__main__":
    sys.exit(main())
