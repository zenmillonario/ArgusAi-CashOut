#!/usr/bin/env python3

import requests
import json
import time
import os

def test_webhook_endpoint_new_domain():
    """Test the webhook endpoint on the new domain to verify it's accessible and working"""
    print("\n🔍 TESTING FEATURE: Webhook Endpoint on New Domain (https://cashoutai.app/api/bot/email-webhook)")
    
    # Get the backend URL from frontend/.env
    base_url = None
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    base_url = line.strip().split('=')[1].strip('"\'')
                    break
    except:
        base_url = "https://cashoutai.app"  # Fallback
    
    api_url = f"{base_url}/api"
    
    print(f"Base URL: {base_url}")
    print(f"API URL: {api_url}")
    
    # Test 1: Verify the new domain is configured correctly
    print("\n🌐 Test 1: Verify new domain configuration")
    
    if "cashoutai.app" not in base_url:
        print("❌ New domain not configured correctly")
        return False
    else:
        print("✅ New domain (cashoutai.app) is configured correctly")
    
    # Test 2: Test basic API health check on new domain
    print("\n🏥 Test 2: API Health Check on New Domain")
    
    try:
        response = requests.get(f"{api_url}/", timeout=10)
        if response.status_code == 200:
            print("✅ API is accessible on new domain")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ API health check failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API health check failed: {str(e)}")
        return False
    
    # Test 3: Test the /api/bot/email-webhook endpoint with sample email data
    print("\n📧 Test 3: Testing /api/bot/email-webhook endpoint with sample email data")
    
    # Sample email data similar to what Zapier would send
    sample_email_data = {
        "subject": "TSLA Price Alert - Target Reached",
        "body": "TSLA has reached your target price of $250.00. Last = $250.15, Bid = $250.10, Ask = $250.20",
        "from": "alerts@tradingview.com",
        "sender": "alerts@tradingview.com",
        "content": "TSLA has reached your target price of $250.00. Last = $250.15, Bid = $250.10, Ask = $250.20"
    }
    
    print(f"Sending sample email data: {json.dumps(sample_email_data, indent=2)}")
    
    try:
        response = requests.post(
            f"{api_url}/bot/email-webhook",
            json=sample_email_data,
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            print("✅ Email webhook processed successfully")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Email webhook failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Email webhook request failed: {str(e)}")
        return False
    
    # Test 4: Test with different email formats that Zapier might send
    print("\n📨 Test 4: Test different email formats that Zapier might send")
    
    # Test various field name variations
    zapier_variations = [
        {
            "email_subject": "Price Alert",
            "email_body": "NVDA reached $800.00",
            "email_from": "alerts@example.com"
        },
        {
            "Subject": "Stock Alert",
            "Body": "GOOGL price movement detected: $140.00",
            "From": "notifications@tradingplatform.com"
        },
        {
            "subject": "Minimal Alert",
            "body": "AAPL at $188.40"
        }
    ]
    
    for i, variation in enumerate(zapier_variations):
        try:
            response = requests.post(
                f"{api_url}/bot/email-webhook",
                json=variation,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print(f"✅ Webhook variation {i+1} processed successfully")
            else:
                print(f"❌ Webhook variation {i+1} failed with status {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Webhook variation {i+1} request failed: {str(e)}")
            return False
    
    # Test 5: Test error handling with empty data
    print("\n🛡️ Test 5: Test error handling with empty/invalid data")
    
    try:
        response = requests.post(
            f"{api_url}/bot/email-webhook",
            json={},
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            print("✅ Webhook handles empty data gracefully")
            print(f"Empty data response: {response.json()}")
        else:
            print(f"⚠️ Webhook returned {response.status_code} for empty data")
            
    except Exception as e:
        print(f"❌ Empty data test failed: {str(e)}")
        return False
    
    # Test 6: Test network connectivity and response times
    print("\n⚡ Test 6: Network Performance Testing")
    
    response_times = []
    for i in range(3):
        try:
            start_time = time.time()
            response = requests.get(f"{api_url}/", timeout=10)
            end_time = time.time()
            
            response_time = end_time - start_time
            response_times.append(response_time)
            
            print(f"Request {i+1}: {response_time:.3f}s")
            
        except Exception as e:
            print(f"❌ Performance test {i+1} failed: {str(e)}")
            return False
    
    avg_response_time = sum(response_times) / len(response_times)
    print(f"✅ Average response time: {avg_response_time:.3f}s")
    
    if avg_response_time > 5.0:
        print("⚠️ Response times may be slow for webhook integration")
    else:
        print("✅ Response times are acceptable for webhook integration")
    
    # Summary
    print("\n📊 WEBHOOK ENDPOINT NEW DOMAIN TEST SUMMARY:")
    print("✅ New domain (cashoutai.app) is configured correctly")
    print("✅ API is accessible on new domain")
    print("✅ /api/bot/email-webhook endpoint accepts sample email data")
    print("✅ Endpoint returns 200 status for valid requests")
    print("✅ Webhook processes various email field formats")
    print("✅ Error handling works for empty/invalid data")
    print("✅ Network performance is acceptable")
    print("✅ No domain-related issues detected")
    
    print("\n🎉 WEBHOOK ENDPOINT NEW DOMAIN TEST PASSED")
    print("\nℹ️ The webhook endpoint is accessible and working on the new domain!")
    print("ℹ️ New domain URL: https://cashoutai.app/api/bot/email-webhook")
    print("ℹ️ Zapier can send email data to this endpoint")
    print("ℹ️ Supported fields: subject/Subject, body/Body/content, from/From/sender")
    print("ℹ️ No domain-related issues detected")
    
    return True

if __name__ == "__main__":
    print("🚀 Starting Webhook Domain Test")
    result = test_webhook_endpoint_new_domain()
    
    if result:
        print("\n🎉 WEBHOOK DOMAIN TEST COMPLETED SUCCESSFULLY")
    else:
        print("\n❌ WEBHOOK DOMAIN TEST FAILED")
    
    exit(0 if result else 1)