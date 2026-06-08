# 📞 AI Voice Receptionist Agent — VAPI & Supabase

A production-ready AI voice agent that answers real phone calls, checks appointment availability in real-time, and books appointments autonomously through natural conversation. Built with **VAPI Voice AI** and **Supabase Edge Functions**.

## 🏗️ Architecture

```
                    ┌──────────────┐
  Phone Call ──────►│   VAPI       │
  (Real Number)     │  Voice AI    │
                    │  Platform    │
                    └──────┬───────┘
                           │ Tool Call (Webhook)
                           ▼
                    ┌──────────────────┐
                    │  Supabase Edge   │
                    │  Function (Deno) │
                    │  vapi-webhook    │
                    └──────┬───────────┘
                           │ Query / Insert
                           ▼
                    ┌──────────────┐
                    │  PostgreSQL  │
                    │  (Supabase)  │
                    │              │
                    │ appointments │
                    └──────────────┘
```

## 🔧 Tools (Function Calling)

| Tool | Description |
|------|-------------|
| `check_availability` | Queries the database for available appointment slots on a given date (9 AM - 5 PM) |
| `book_appointment` | Books an appointment with customer name, phone, date, and time |

## 🔄 Conversation Flow

```
1. Agent greets the caller
2. Asks what date they'd like to visit
3. Calls check_availability tool → gets available time slots
4. Presents available times to the caller
5. Caller chooses a time
6. Agent asks for name and phone number
7. Calls book_appointment tool → confirms booking
8. Thanks the caller and ends the call
```

## 📁 Project Structure

```
voice-agent/
├── create_vapi_agent.py              # Setup script — creates VAPI tools & assistant
├── database_setup.sql                # PostgreSQL schema for appointments table
├── .env.example                      # Environment variables template
├── supabase/
│   └── functions/
│       └── vapi-webhook/
│           └── index.ts              # Edge Function — handles VAPI tool calls
```

## 🧩 Key Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Voice AI** | VAPI Platform | Speech-to-Text, Text-to-Speech, conversation management |
| **AI Model** | OpenAI GPT-4o-mini | Natural language understanding and response generation |
| **Webhook** | Supabase Edge Functions (Deno) | Serverless handler for VAPI tool calls |
| **Database** | PostgreSQL (Supabase) | Appointment storage with unique constraints |
| **Setup** | Python script | Automated creation of VAPI tools and assistant |

## 🛡️ Features

- **Multi-format Payload Support**: Handles both `toolCallList` and `toolWithToolCallList` VAPI formats
- **Dynamic Argument Parsing**: Safely parses arguments whether sent as JSON string or object
- **Duplicate Prevention**: PostgreSQL unique constraint prevents double-booking
- **JWT-free Deployment**: Public endpoint for VAPI webhook access
- **Comprehensive Logging**: Detailed logs for debugging webhook interactions

## ⚡ Tech Stack

- **Voice Platform**: VAPI (Voice AI)
- **AI Model**: OpenAI GPT-4o-mini
- **Serverless**: Supabase Edge Functions (Deno runtime)
- **Database**: PostgreSQL (Supabase)
- **Setup Script**: Python + requests

## 🚀 Getting Started

### Prerequisites
- [Supabase](https://supabase.com) account
- [VAPI](https://vapi.ai) account
- Supabase CLI (`npx supabase`)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/beko2499/voice-agent.git
cd voice-agent

# 2. Create .env file
cp .env.example .env
# Edit .env with your VAPI and Supabase keys

# 3. Run the database setup SQL in Supabase SQL Editor
# Paste content of database_setup.sql

# 4. Deploy the Edge Function
npx supabase login
npx supabase functions deploy vapi-webhook --project-ref YOUR_PROJECT_REF --no-verify-jwt

# 5. Create the VAPI agent
pip install requests python-dotenv
python create_vapi_agent.py

# 6. Get a phone number from VAPI Dashboard
# Go to https://dashboard.vapi.ai/phone-numbers
# Buy a number and assign it to "Clinic Receptionist AI"
```

### Test It
Call the assigned phone number and try booking an appointment!

## 📊 Database Schema

```sql
CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_name TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    status TEXT DEFAULT 'CONFIRMED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_appointment_datetime 
        UNIQUE (appointment_date, appointment_time)
);
```

## 📄 License

MIT
