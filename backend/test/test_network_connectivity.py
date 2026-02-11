"""
Network diagnostic tool for MongoDB Atlas connectivity.

Tests if we can reach the MongoDB servers at all.
"""

import socket
import sys


def test_host_port(host: str, port: int, timeout: int = 5) -> bool:
    """Test if a host:port is reachable."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except socket.gaierror:
        return False
    except Exception as e:
        print(f"   Error: {e}")
        return False


def main():
    print("\n🔍 MongoDB Network Connectivity Test\n")
    print("=" * 50)
    
    # MongoDB Atlas shard hosts
    hosts = [
        "ac-qphx-shard-00-00.rx4w7xy.mongodb.net",
        "ac-qphx-shard-00-01.rx4w7xy.mongodb.net",
        "ac-qphx-shard-00-02.rx4w7xy.mongodb.net",
    ]
    
    port = 27017
    
    print(f"\n📡 Testing connectivity to MongoDB Atlas shards...")
    print(f"   Port: {port}")
    print(f"   Timeout: 5 seconds\n")
    
    all_reachable = True
    
    for host in hosts:
        print(f"Testing {host}:{port}...", end=" ")
        
        if test_host_port(host, port):
            print("✅ REACHABLE")
        else:
            print("❌ UNREACHABLE")
            all_reachable = False
    
    print("\n" + "=" * 50)
    
    if all_reachable:
        print("\n✅ All MongoDB servers are reachable!")
        print("\n🔍 Next steps:")
        print("   1. Check if cluster is PAUSED in Atlas")
        print("   2. Verify IP whitelist includes your IP")
        print("   3. Confirm replica set name is correct")
        return 0
    else:
        print("\n❌ Cannot reach MongoDB servers!")
        print("\n🔧 Possible causes:")
        print("   1. Firewall blocking port 27017")
        print("   2. Cluster is deleted/doesn't exist")
        print("   3. Wrong shard hostnames")
        print("   4. Network connectivity issues")
        print("\n💡 Try:")
        print("   - Check Atlas dashboard for cluster status")
        print("   - Verify shard hostnames in Atlas")
        print("   - Test from a different network")
        return 1


if __name__ == "__main__":
    sys.exit(main())
