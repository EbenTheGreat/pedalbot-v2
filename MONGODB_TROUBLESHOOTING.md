# MongoDB Atlas Troubleshooting Checklist

## Current Status: Connection Timeout

**Error**: `No replica set members found yet`

This means we're **past the DNS issue** ✅ but hitting a new problem.

---

## 🔍 Possible Causes (in order of likelihood)

### 1. **Cluster is Paused** ⏸️ (Most Likely)

MongoDB Atlas **auto-pauses** free M0 clusters after 60 days of inactivity.

**How to check**:
1. Go to https://cloud.mongodb.com/
2. Look at your cluster status
3. If it says **"PAUSED"** → Click **"Resume"**
4. Wait 2-3 minutes for it to start

---

### 2. **Wrong Replica Set Name** 🏷️

The replica set name I guessed: `atlas-pedalbot-cluster-shard-0`

**How to find the correct name**:
1. In Atlas, click on your cluster
2. Look for **"Replica Set Name"** in cluster details
3. It might be something like:
   - `atlas-xxxxx-shard-0`
   - `Cluster0-shard-0`
   - Or just `rs0`

**If different**, update `.env`:
```env
MONGODB_URI=mongodb://...?replicaSet=<CORRECT_NAME>&...
```

---

### 3. **IP Whitelist** 🔒

Your IP might not be whitelisted.

**How to fix**:
1. Atlas → **Network Access**
2. Click **"Add IP Address"**
3. Choose **"Allow Access from Anywhere"** (0.0.0.0/0)
4. Save

⚠️ **Note**: This is fine for development, but restrict it in production!

---

### 4. **Firewall Blocking Port 27017** 🚫

Less likely, but possible.

**How to test**:
```bash
telnet ac-qphx-shard-00-00.rx4w7xy.mongodb.net 27017
```

If it times out → firewall issue.

---

## ✅ Quick Fix Steps (Do These Now)

### Step 1: Check Cluster Status
Go to Atlas and verify the cluster is **RUNNING** (not paused).

### Step 2: Verify IP Whitelist
Add `0.0.0.0/0` to Network Access (temporary).

### Step 3: Get Exact Replica Set Name
Find it in cluster details and update if needed.

### Step 4: Test Again
```bash
uv run python -m backend.test.test_mongodb_connection
```

---

## 🎯 Most Likely Solution

**Your cluster is probably paused.**

Free M0 clusters pause after inactivity. Just click **"Resume"** in Atlas and wait 2-3 minutes.

Then test again!

---

## Alternative: Create Fresh Cluster (5 minutes)

If the old cluster is gone or you can't access it:

1. **Create new M0 cluster** at https://cloud.mongodb.com/
2. **Get connection string** (it will show both SRV and standard)
3. **Update `.env`** with the new URI
4. **Add IP whitelist**: 0.0.0.0/0
5. **Test connection**

This is often faster than debugging an old cluster.
