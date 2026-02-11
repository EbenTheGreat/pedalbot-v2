# Get Standard MongoDB Connection String

Your new cluster has the same DNS SRV issue. We need to convert to standard format.

## 🔍 How to Get Shard Hostnames from Atlas

### Method 1: Atlas UI (Recommended)
1. Go to https://cloud.mongodb.com/
2. Click on your **"pedalbot"** cluster
3. Click **"Connect"**
4. Choose **"Connect using MongoDB Compass"**
5. Look for the connection string - it will show the actual shard hosts

### Method 2: Use MongoDB Compass
1. Download MongoDB Compass (if you don't have it)
2. Try to connect with the SRV string
3. It will show you the resolved hosts

### Method 3: Manual Construction (If you can't find it)

Based on the pattern, your standard URI should be:

```
mongodb://olasunkanmitijani40_db_user:KCVYPCPW6ZloXsDL@pedalbot-shard-00-00.eejq7lp.mongodb.net:27017,pedalbot-shard-00-01.eejq7lp.mongodb.net:27017,pedalbot-shard-00-02.eejq7lp.mongodb.net:27017/pedalbot_db?ssl=true&replicaSet=atlas-pedalbot-shard-0&authSource=admin&retryWrites=true&w=majority
```

**Note**: The shard prefix might be different. Common patterns:
- `pedalbot-shard-00-XX`
- `cluster0-shard-00-XX`  
- `ac-XXXXX-shard-00-XX`

## 🚀 Quick Fix

I'll update your `.env` with the most likely standard URI format. If it doesn't work, you'll need to get the exact shard hostnames from Atlas.

## ⚡ Alternative: Change DNS Settings

If you want SRV to work, change your system DNS to:
- Primary: `1.1.1.1` (Cloudflare)
- Secondary: `8.8.8.8` (Google)

Then restart Docker and try again.
