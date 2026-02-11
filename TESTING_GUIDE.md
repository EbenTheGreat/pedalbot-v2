# Testing Guide for PedalBot Background Workers

This guide walks you through testing all Celery background workers after setting up Docker.

## ✅ Prerequisites

- Docker services running: `docker-compose ps`
- All services should show "Up" status
- Flower dashboard accessible at http://localhost:5555

## 🧪 Test Sequence

### 1. Email Worker Tests ✅ (COMPLETED)

You've already tested:
- ✅ Welcome emails
- ✅ Manual processed notifications
- ✅ Price alert emails
- ✅ Bulk emails

**Verify**: Check https://resend.com/emails to see sent emails

---

### 2. PDF Ingestion Worker Tests 🔄 (NEXT)

Test the manual upload and processing pipeline.

**What it does:**
- Uploads PDF manuals
- Extracts text using OCR
- Chunks the content
- Embeds chunks with VoyageAI
- Stores in Pinecone vector database

**Test file:** `backend/test/test_ingest_worker.py`

**Run:**
```bash
docker-compose build --no-cache
```

**Expected behavior:**
1. Task queued in Celery
2. PDF processed (OCR + chunking)
3. Embeddings created
4. Stored in Pinecone
5. Email notification sent (if configured)

**Monitor:**
- Flower: http://localhost:5555 (task progress)
- Logs: `docker-compose logs -f celery-worker`

---

### 3. Pricing Worker Tests 🔄 (AFTER INGESTION)

Test Reverb API integration for pricing data.

**What it does:**
- Fetches current market prices from Reverb
- Updates pricing in MongoDB
- Checks price alerts
- Sends notifications when prices drop

**Test file:** `backend/test/test_pricing_worker.py`

**Run:**
```bash
uv run python -m backend.test.test_pricing_worker
```

**Expected behavior:**
1. Queries Reverb API for pedal prices
2. Updates MongoDB with latest prices
3. Checks if any price alerts triggered
4. Sends email if price dropped below target

---

### 4. Scheduled Tasks (Celery Beat) 🔄 (ONGOING)

Test periodic background jobs.

**Configured schedules:**
- **Daily at 2 AM**: Refresh all pricing data
- **Weekly (Monday 3 AM)**: Clean up old job records

**Test manually:**
```bash
# Trigger pricing refresh manually
uv run python -c "from backend.workers.pricing_worker import refresh_all_pricing_task; refresh_all_pricing_task.delay()"

# Trigger cleanup manually
uv run python -c "from backend.workers.ingest_worker import cleanup_old_jobs_task; cleanup_old_jobs_task.delay()"
```

**Verify Beat is running:**
```bash
docker-compose logs celery-beat
```

---

## 🔍 Monitoring & Debugging

### Flower Dashboard (http://localhost:5555)
- **Tasks**: View all task history
- **Workers**: Check worker status and performance
- **Monitor**: Real-time task execution

### Docker Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f celery-worker
docker-compose logs -f celery-beat
docker-compose logs -f redis
```

### Redis CLI
```bash
# Access Redis
docker-compose exec redis redis-cli

# Check queue lengths
LLEN celery
LLEN notifications
LLEN ingestion
LLEN pricing

# View all keys
KEYS *
```

---

## 🐛 Common Issues

### Issue: Tasks not processing
**Solution:**
```bash
docker-compose restart celery-worker
docker-compose logs -f celery-worker
```

### Issue: Redis connection errors
**Solution:**
```bash
docker-compose ps redis  # Check if running
docker-compose exec redis redis-cli ping  # Should return PONG
```

### Issue: Email not sending
**Check:**
1. `RESEND_API_KEY` is set in `.env`
2. `RESEND_FROM_EMAIL=onboarding@resend.dev` (for testing)
3. Check Resend dashboard for delivery status

### Issue: PDF ingestion failing
**Check:**
1. `GOOGLE_VISION_CREDENTIALS` is set (for OCR)
2. `PINECONE_API_KEY` is set
3. `VOYAGEAI_API_KEY` is set (for embeddings)
4. PDF file exists and is readable

---

## 📊 Success Criteria

### Email Worker ✅
- [x] Emails appear in Flower as "SUCCESS"
- [x] Emails visible in Resend dashboard
- [x] Email templates render correctly (HTML)

### Ingestion Worker
- [ ] PDF uploaded successfully
- [ ] OCR extracts text correctly
- [ ] Chunks created (visible in logs)
- [ ] Embeddings generated
- [ ] Stored in Pinecone
- [ ] Notification email sent

### Pricing Worker
- [ ] Reverb API returns pricing data
- [ ] Prices updated in MongoDB
- [ ] Price alerts checked
- [ ] Alert emails sent when triggered

### Celery Beat
- [ ] Beat scheduler running
- [ ] Scheduled tasks appear in Flower
- [ ] Tasks execute at correct times

---

## 🚀 Next Steps After Testing

1. **Integration Testing**: Test the full user flow
   - User uploads PDF → Gets email when processed
   - User sets price alert → Gets email when price drops

2. **Performance Testing**: Test with multiple concurrent tasks
   - Upload multiple PDFs simultaneously
   - Check worker concurrency settings

3. **Error Handling**: Test failure scenarios
   - Invalid PDF files
   - API failures (Reverb, Pinecone, etc.)
   - Network timeouts

4. **Production Readiness**:
   - Set up proper domain for emails (verify on Resend)
   - Configure environment-specific settings
   - Set up monitoring/alerting
   - Review resource limits in docker-compose.yml

---

## 📝 Test Results Template

Copy this to track your testing:

```
## Test Results - [Date]

### Email Worker
- Welcome email: ✅/❌
- Manual processed: ✅/❌
- Price alert: ✅/❌
- Bulk emails: ✅/❌

### Ingestion Worker
- PDF upload: ✅/❌
- OCR extraction: ✅/❌
- Chunking: ✅/❌
- Embeddings: ✅/❌
- Pinecone storage: ✅/❌

### Pricing Worker
- Reverb API: ✅/❌
- Price updates: ✅/❌
- Alert checking: ✅/❌

### Celery Beat
- Scheduler running: ✅/❌
- Daily pricing refresh: ✅/❌
- Weekly cleanup: ✅/❌

### Notes:
[Add any issues or observations here]
```
