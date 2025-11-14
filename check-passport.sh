#!/bin/bash

# ---------------------------
# Slack webhook URL
# ---------------------------
SLACK_WEBHOOK="https://hooks.slack.com/services/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"

send_slack() {
  # $1 = message to send
  local timestamp
  timestamp=$(date '+%Y-%m-%d %H:%M:%S')
  curl -s -X POST -H 'Content-type: application/json' \
    --data "{\"text\":\"[$timestamp] $1\"}" \
    "$SLACK_WEBHOOK"
}

echo "🔍 Checking passport slot availability..."
echo "=========================================="
echo ""

for i in {1..30}; do
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "⏳ Attempt $i of 30 at $timestamp..."
    
    response=$(curl -s --max-time 10 \
      'https://emrtds.nepalpassport.gov.np/iups-api/calendars/77/false' \
      -H 'Accept: application/json, text/plain, */*' \
      -H 'Accept-Language: en-US,en;q=0.9' \
      -H 'Cache-Control: no-cache' \
      -H 'Connection: keep-alive' \
      -H 'Referer: https://emrtds.nepalpassport.gov.np/' \
      -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' \
      --compressed 2>&1)
    
    # Waiting room detected
    if echo "$response" | grep -q "Online Waiting Room"; then
        echo "⚠️ HIGH TRAFFIC - Website has a waiting queue"
        send_slack "⚠️ Passport site has a waiting room active. Try later."
        exit 1

    # Got valid JSON
    elif echo "$response" | grep -q "offDates"; then
        echo "✅ Success! Got response:"
        echo "$response" | jq . 2>/dev/null || echo "$response"
        
        # Slots available
        if echo "$response" | grep -q '"offDates":\[\]'; then
            echo "🎉 SLOTS ARE AVAILABLE!"
            send_slack "🎉 SLOTS AVAILABLE for passport application! Check now: https://emrtds.nepalpassport.gov.np/"
        else
            echo "❌ NO SLOTS AVAILABLE - Date is marked as off"
        fi
        exit 0

    # Connection or other errors
    else
        echo "❌ Connection failed at $timestamp. Retrying in 3 seconds..."
        sleep 3
    fi
done

timestamp=$(date '+%Y-%m-%d %H:%M:%S')
echo ""
echo "⛔ All attempts failed at $timestamp. Possible reasons: site down, high traffic, network issues"
send_slack "⛔ Passport check failed. Possible reasons: site down or high traffic."
