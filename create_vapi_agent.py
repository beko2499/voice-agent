# -*- coding: utf-8 -*-
"""
Voice Agent Setup Script
Creates tools and assistant on Vapi, sets up Supabase database.
"""
import requests
import json
import sys
import io
import os
from dotenv import load_dotenv

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load environment variables from .env file
load_dotenv()

VAPI_API_KEY = os.getenv("VAPI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
EDGE_FUNCTION_URL = f"{SUPABASE_URL}/functions/v1/vapi-webhook"

if not all([VAPI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY]):
    print("ERROR: Missing environment variables. Copy .env.example to .env and fill in your keys.")
    sys.exit(1)

vapi_headers = {
    "Authorization": f"Bearer {VAPI_API_KEY}",
    "Content-Type": "application/json"
}

# ============================================
# STEP 0: Clean up any existing assistants
# ============================================
print("STEP 0: Cleaning up old assistants...")
try:
    existing = requests.get("https://api.vapi.ai/assistant", headers=vapi_headers)
    if existing.status_code == 200:
        for a in existing.json():
            if 'Clinic' in a.get('name', '') or 'Receptionist' in a.get('name', ''):
                requests.delete(f"https://api.vapi.ai/assistant/{a['id']}", headers=vapi_headers)
                print(f"  Deleted old assistant: {a['name']} ({a['id']})")
except Exception as e:
    print(f"  Cleanup skipped: {e}")

# ============================================
# STEP 1: Create Tools separately via /tool
# ============================================
print("\nSTEP 1: Creating tools on Vapi...")

# Tool 1: Check Availability
tool1_payload = {
    "type": "function",
    "function": {
        "name": "check_availability",
        "description": "Checks the database for available appointment times on a specific date. Returns a list of available time slots.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "The date to check availability for, in YYYY-MM-DD format. For example: 2026-06-08"
                }
            },
            "required": ["date"]
        }
    },
    "server": {
        "url": EDGE_FUNCTION_URL
    }
}

r1 = requests.post("https://api.vapi.ai/tool", headers=vapi_headers, json=tool1_payload)
if r1.status_code in [200, 201]:
    tool1_id = r1.json()["id"]
    print(f"  [OK] check_availability tool created. ID: {tool1_id}")
else:
    print(f"  [FAIL] check_availability: {r1.status_code} - {r1.text[:300]}")
    sys.exit(1)

# Tool 2: Book Appointment
tool2_payload = {
    "type": "function",
    "function": {
        "name": "book_appointment",
        "description": "Books an appointment for a customer in the database. Call this after confirming the date and time with the customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "The full name of the customer."
                },
                "phone_number": {
                    "type": "string",
                    "description": "The phone number of the customer."
                },
                "date": {
                    "type": "string",
                    "description": "The date of the appointment in YYYY-MM-DD format."
                },
                "time": {
                    "type": "string",
                    "description": "The time of the appointment in HH:MM format (24-hour). For example: 14:00"
                }
            },
            "required": ["customer_name", "phone_number", "date", "time"]
        }
    },
    "server": {
        "url": EDGE_FUNCTION_URL
    }
}

r2 = requests.post("https://api.vapi.ai/tool", headers=vapi_headers, json=tool2_payload)
if r2.status_code in [200, 201]:
    tool2_id = r2.json()["id"]
    print(f"  [OK] book_appointment tool created. ID: {tool2_id}")
else:
    print(f"  [FAIL] book_appointment: {r2.status_code} - {r2.text[:300]}")
    sys.exit(1)

# ============================================
# STEP 2: Create the Assistant with toolIds
# ============================================
print("\nSTEP 2: Creating assistant on Vapi...")

assistant_payload = {
    "name": "Clinic Receptionist AI",
    "voice": {
        "provider": "vapi",
        "voiceId": "Elliot"
    },
    "model": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a professional and friendly receptionist at 'Al-Noor Medical Clinic' in Dubai. "
                    "You speak clearly in English. Your job is to help patients book appointments.\n\n"
                    "WORKFLOW:\n"
                    "1. Greet the caller warmly.\n"
                    "2. Ask what date they would like to visit the clinic.\n"
                    "3. Use the 'check_availability' tool to find available times for that date.\n"
                    "4. Tell the caller the available times and ask them to choose one.\n"
                    "5. Once they choose a time, ask for their full name and phone number.\n"
                    "6. Use the 'book_appointment' tool to register the appointment.\n"
                    "7. Confirm the booking details and thank them.\n\n"
                    "RULES:\n"
                    "- Always use the tools to check availability before suggesting times.\n"
                    "- Never make up available times.\n"
                    "- If all slots are booked, suggest trying another date.\n"
                    "- Keep responses concise and conversational."
                )
            }
        ],
        "toolIds": [tool1_id, tool2_id]
    },
    "firstMessage": "Hello! Welcome to Al-Noor Medical Clinic. How can I help you today? Would you like to book an appointment?"
}

r3 = requests.post("https://api.vapi.ai/assistant", headers=vapi_headers, json=assistant_payload)
if r3.status_code in [200, 201]:
    assistant = r3.json()
    print(f"  [OK] Assistant created!")
    print(f"  Assistant ID: {assistant['id']}")
    print(f"  Name: {assistant['name']}")
else:
    print(f"  [FAIL] Assistant creation failed: {r3.status_code}")
    print(f"  Response: {r3.text[:500]}")
    sys.exit(1)

# ============================================
# STEP 3: Setup Supabase Database
# ============================================
print("\nSTEP 3: Setting up Supabase database...")

supabase_headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# Execute SQL via Supabase REST RPC (using the pg_query approach)
# First, let's try using the Supabase Management API to run SQL
# Actually, the simplest way is to use the REST API to check if table exists
# and create via SQL Editor in dashboard if not.

# Let's check if the table exists by trying to query it
test_r = requests.get(
    f"{SUPABASE_URL}/rest/v1/appointments?select=count",
    headers={
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Prefer": "count=exact"
    }
)

if test_r.status_code == 200:
    print("  [OK] appointments table already exists!")
elif test_r.status_code == 404 or "does not exist" in test_r.text.lower() or test_r.status_code >= 400:
    print("  [WARNING] appointments table not found.")
    print("  You need to run the SQL script in Supabase SQL Editor.")
    print("  Go to: https://supabase.com/dashboard/project/uortdcafgbjbfgihptea/sql/new")
    print("  And paste the content of: c:\\betar\\voice-agent\\database_setup.sql")
else:
    print(f"  Table check response: {test_r.status_code} - {test_r.text[:200]}")

# ============================================
# SUMMARY
# ============================================
print("\n" + "="*60)
print("SETUP COMPLETE!")
print("="*60)
print(f"\nAssistant: {assistant['name']}")
print(f"Assistant ID: {assistant['id']}")
print(f"Tool 1 (check_availability): {tool1_id}")
print(f"Tool 2 (book_appointment): {tool2_id}")
print(f"Edge Function URL: {EDGE_FUNCTION_URL}")
print(f"\nTO TEST:")
print(f"  1. Make sure the Edge Function is deployed on Supabase")
print(f"  2. Make sure the SQL has been run to create the table")
print(f"  3. Go to https://dashboard.vapi.ai/assistants")
print(f"  4. Click on 'Clinic Receptionist AI'")
print(f"  5. Click 'Talk' to start a voice call!")
