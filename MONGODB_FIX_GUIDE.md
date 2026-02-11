# MongoDB Connection Issue - Diagnosis & Fix

## ❌ Current Problem

**Error**: `ConfigurationError: The resolution lifetime expired after 21.426 seconds`

**Root Cause**: DNS cannot resolve the MongoDB Atlas hostname:
```
_mongodb._tcp.pedalbot-cluster.rx4w7xy.mongodb.net
```

This means the DNS servers cannot find your MongoDB cluster.

---

## 🔍 Diagnosis Results

### What We Fixed:
✅ Changed `MONGODB_URL` to `MONGODB_URI` in `.env` (config mismatch)
✅ Updated test files to use correct variable names

### What's Still Broken:
❌ MongoDB Atlas cluster is not accessible
❌ DNS resolution failing

---

## 🛠️ How to Fix

### Option 1: Check MongoDB Atlas Dashboard (Recommended)

1. **Go to MongoDB Atlas**: https://cloud.mongodb.com/
2. **Log in** with your account
3. **Check your cluster status**:
   - Is the cluster **paused**? → Resume it
   - Does the cluster **exist**? → If deleted, create a new one
   - Is it in the **correct project**?

4. **Get the correct connection string**:
   - Click "Connect" on your cluster
   - Choose "Connect your application"
   - Copy the connection string
   - Update `.env` with the new `MONGODB_URI`

5. **Check IP Whitelist**:
   - Go to "Network Access"
   - Add your current IP address
   - Or allow access from anywhere: `0.0.0.0/0` (for testing only!)

### Option 2: Use a Different MongoDB Instance

If you don't have access to the Atlas cluster:

1. **Create a new free cluster**:
   - Go to https://www.mongodb.com/cloud/atlas/register
   - Create a free M0 cluster
   - Get the connection string
   - Update `MONGODB_URI` in `.env`

2. **Use local MongoDB** (for development):
   ```bash
   # Install MongoDB locally
   # Then update .env:
   MONGODB_URI=mongodb://localhost:27017/pedalbot_db
   ```

### Option 3: Skip MongoDB for Now

For testing Celery workers without MongoDB:

- ✅ **Email worker** - Already working! No MongoDB needed
- ⚠️ **Pricing worker** - Needs MongoDB to store pricing data
- ⚠️ **Ingestion worker** - Needs MongoDB to store manual metadata

You can continue testing emails and come back to MongoDB later.

---

## 📝 Next Steps

### Immediate (Do Now):

1. **Check MongoDB Atlas Dashboard**
   - Verify cluster exists and is running
   - Get correct connection string
   - Update IP whitelist

2. **Update `.env` if needed**
   ```bash
   MONGODB_URI=<your-new-connection-string>
   ```

3. **Test connection again**:
   ```bash
   uv run python -m backend.test.test_mongodb_connection
   ```

### After MongoDB is Fixed:

1. **Test pricing worker**:
   ```bash
   uv run python -m backend.test.test_pricing_worker
   ```

2. **Test ingestion worker**:
   ```bash
   uv run python -m backend.test.test_ingest_worker
   ```

---

## ✅ What's Already Working

While MongoDB is down, you still have:

- ✅ **Docker services** running
- ✅ **Redis** working
- ✅ **Celery workers** processing tasks
- ✅ **Email system** fully functional
- ✅ **Flower dashboard** at http://localhost:5555

**Your background job infrastructure is solid!** MongoDB is just one piece.

---

## 🆘 If You're Stuck

**Can't access MongoDB Atlas?**
- Create a new free cluster (takes 5 minutes)
- Or use local MongoDB for development

**Don't want to deal with MongoDB right now?**
- That's fine! Your email workers are fully tested
- You can deploy those features without MongoDB
- Come back to pricing/ingestion later

**Need help?**
- MongoDB Atlas docs: https://docs.atlas.mongodb.com/
- Connection troubleshooting: https://docs.atlas.mongodb.com/troubleshoot-connection/
