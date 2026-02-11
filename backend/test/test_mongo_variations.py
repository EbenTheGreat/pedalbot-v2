"""Test different MongoDB connection string formats to isolate SSL issues.
""" 


from pymongo import MongoClient
import ssl

# Different connection string variations to test
test_configs = [
    {
        "name": "Standard with tlsAllowInvalidCertificates",
        "uri": "mongodb+srv://antigravity:h1RvJKgXxEahgIKv@pedalbot.prrqtm2.mongodb.net/?appName=pedalbot",
        "options": {
            "tls": True,
            "tlsAllowInvalidCertificates": True,
            "serverSelectionTimeoutMS": 10000
        }
    },
    {
        "name": "With retryWrites=false",
        "uri": "mongodb+srv://antigravity:h1RvJKgXxEahgIKv@pedalbot.prrqtm2.mongodb.net/?retryWrites=false&appName=pedalbot",
        "options": {
            "tls": True,
            "tlsAllowInvalidCertificates": True,
            "serverSelectionTimeoutMS": 10000
        }
    },
    {
        "name": "With tlsInsecure",
        "uri": "mongodb+srv://antigravity:h1RvJKgXxEahgIKv@pedalbot.prrqtm2.mongodb.net/?appName=pedalbot",
        "options": {
            "tlsInsecure": True,
            "serverSelectionTimeoutMS": 10000
        }
    },
]

print(f"OpenSSL version: {ssl.OPENSSL_VERSION}\n")

for config in test_configs:
    print(f"Testing: {config['name']}")
    print(f"URI: {config['uri'][:60]}...")
    
    try:
        client = MongoClient(config['uri'], **config['options'])
        client.admin.command('ping')
        print("SUCCESS Connection established!")
        
        # List databases
        dbs = client.list_database_names()
        print(f"Available databases: {dbs}\n")
        
        client.close()
        break  # Stop on first success
        
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        print(f"FAILED: {error_msg}\n")

print("\nDone testing connection variations.")
