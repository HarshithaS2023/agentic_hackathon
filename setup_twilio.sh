#!/bin/bash
# setup_twilio.sh - Quick setup script for Twilio integration

set -e

echo "🚀 Twilio SMS Integration Setup"
echo "================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+"
    exit 1
fi

echo "✅ Python found: $(python3 --version)"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements-twilio.txt

echo ""
echo "🔑 Twilio Credentials Setup"
echo "=============================="
echo ""
echo "Get your credentials from https://www.twilio.com/console"
echo ""

# Prompt for credentials
read -p "Enter your Twilio Account SID: " ACCOUNT_SID
read -p "Enter your Twilio Auth Token: " AUTH_TOKEN
read -p "Enter your Twilio Phone Number (e.g., +1234567890): " PHONE_NUMBER

# Create .env file
cat > .env << EOF
export TWILIO_ACCOUNT_SID="$ACCOUNT_SID"
export TWILIO_AUTH_TOKEN="$AUTH_TOKEN"
export TWILIO_PHONE_NUMBER="$PHONE_NUMBER"
EOF

echo ""
echo "✅ Credentials saved to .env"
echo ""

# Load the environment
set -a
source .env
set +a

echo "📋 Configuration Summary"
echo "========================"
echo "Account SID: ${TWILIO_ACCOUNT_SID:0:15}..."
echo "Phone Number: $TWILIO_PHONE_NUMBER"
echo ""

echo "🌐 Next Steps:"
echo "1. Install ngrok: https://ngrok.com/download"
echo "2. Start the server: python twilio_integration.py"
echo "3. In another terminal: ngrok http 5000"
echo "4. Update Twilio webhook to your ngrok URL (https://yourngrok.ngrok.io/sms)"
echo "5. Text your Twilio number to test!"
echo ""

echo "📖 For more details, see TWILIO_SETUP.md"
