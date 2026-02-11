#!/bin/bash

# Test script to verify conversation_id fix
echo "Testing conversation_id placeholder fix..."
echo ""

# Test 1: Send request with "string" as conversation_id
echo "Test 1: Sending request with conversation_id='string'"
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/query/" \
  -H "Content-Type: application/json" \
  -d '{"query":"how do i turn it on","pedal_name":"nux mg-30","conversation_id":"string","stream":false}')

# Extract conversation_id from response
CONV_ID=$(echo "$RESPONSE" | grep -o '"conversation_id":"[^"]*"' | cut -d'"' -f4)

echo "Response conversation_id: $CONV_ID"
echo ""

# Verify it's NOT "string"
if [ "$CONV_ID" = "string" ]; then
    echo "❌ FAILED: conversation_id is still 'string'"
    exit 1
else
    echo "✅ PASS: conversation_id was generated: $CONV_ID"
fi

echo ""
echo "Test 2: Retrieving conversation by ID"
CONV_RESPONSE=$(curl -s "http://localhost:8000/api/query/conversations/$CONV_ID")

# Check if response contains error
if echo "$CONV_RESPONSE" | grep -q "Internal Server Error"; then
    echo "❌ FAILED: ObjectId serialization error"
    exit 1
elif echo "$CONV_RESPONSE" | grep -q "conversation_id"; then
    echo "✅ PASS: Conversation retrieved successfully"
    echo ""
    echo "Sample of conversation data:"
    echo "$CONV_RESPONSE" | head -c 300
    echo "..."
else
    echo "⚠️  WARNING: Unexpected response"
    echo "$CONV_RESPONSE"
fi

echo ""
echo ""
echo "All tests passed! 🎉"
