#!/usr/bin/env python3
"""
Network scanner to find OpenEVSE wallboxes by detecting Mongoose/6.18 server header.
"""

import socket
import ipaddress
import requests
import concurrent.futures
import sys
from typing import List, Optional

# Disable SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings()

def get_local_network() -> Optional[ipaddress.IPv4Network]:
    """Detect the local network range."""
    try:
        # Create a socket to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Assume /24 subnet
        network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
        return network
    except Exception as e:
        print(f"Error detecting local network: {e}")
        return None

def get_hostname(ip: str) -> str:
    """Get hostname from OpenEVSE device config API."""
    try:
        # Try to get hostname from device's config endpoint
        url = f"http://{ip}/config"
        response = requests.get(url, timeout=2, allow_redirects=False)
        if response.status_code == 200:
            config = response.json()
            # Try different possible hostname fields
            hostname = config.get('hostname') or config.get('device_name') or config.get('name')
            if hostname:
                return hostname
    except Exception:
        pass
    
    # Fallback to reverse DNS lookup
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except (socket.herror, socket.gaierror, socket.timeout):
        return "(unknown)"

def check_host(ip: str) -> Optional[dict]:
    """Check if a host has Mongoose server on port 80."""
    try:
        # Try HTTP request with short timeout
        url = f"http://{ip}"
        response = requests.head(url, timeout=2, allow_redirects=False)
        
        server_header = response.headers.get('Server', '')
        
        if 'Mongoose' in server_header:
            hostname = get_hostname(ip)
            return {
                'ip': ip,
                'hostname': hostname,
                'server': server_header,
                'status': response.status_code,
                'headers': dict(response.headers)
            }
    except (requests.exceptions.RequestException, socket.timeout):
        pass
    except Exception:
        pass
    
    return None

def scan_network(network: ipaddress.IPv4Network, max_workers: int = 50) -> List[dict]:
    """Scan the network for OpenEVSE devices."""
    print(f"Scanning network {network} for OpenEVSE wallboxes...")
    print(f"This may take a minute...\n")
    
    hosts = list(network.hosts())
    found_devices = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all scan tasks
        future_to_ip = {executor.submit(check_host, str(ip)): ip for ip in hosts}
        
        # Process results as they complete
        completed = 0
        for future in concurrent.futures.as_completed(future_to_ip):
            completed += 1
            if completed % 25 == 0:
                print(f"Progress: {completed}/{len(hosts)} hosts checked...", end='\r')
            
            result = future.result()
            if result:
                found_devices.append(result)
                hostname_info = f" ({result['hostname']})" if result['hostname'] != "(unknown)" else ""
                print(f"\n✓ Found OpenEVSE at {result['ip']}{hostname_info} - Server: {result['server']}")
    
    print(f"\nScan complete: checked {len(hosts)} hosts")
    return found_devices

def main():
    print("OpenEVSE Wallbox Network Scanner")
    print("=" * 50)
    
    # Allow custom network range as argument
    if len(sys.argv) > 1:
        try:
            network = ipaddress.IPv4Network(sys.argv[1], strict=False)
            print(f"Using specified network: {network}\n")
        except ValueError as e:
            print(f"Error: Invalid network range '{sys.argv[1]}': {e}")
            sys.exit(1)
    else:
        network = get_local_network()
        if not network:
            print("Could not detect local network. Please specify manually:")
            print("Usage: python3 find_openevse.py [network_range]")
            print("Example: python3 find_openevse.py 192.168.1.0/24")
            sys.exit(1)
        print(f"Detected local network: {network}\n")
    
    # Scan the network
    devices = scan_network(network)
    
    # Display results
    print("\n" + "=" * 50)
    if devices:
        print(f"Found {len(devices)} OpenEVSE device(s):\n")
        for device in devices:
            print(f"  IP Address: {device['ip']}")
            print(f"  Hostname:   {device['hostname']}")
            print(f"  Server:     {device['server']}")
            print(f"  Web UI:     http://{device['ip']}")
            print()
    else:
        print("No OpenEVSE devices found on the network.")
        print("\nTroubleshooting:")
        print("  - Ensure the wallbox is powered on and connected")
        print("  - Check if you're on the correct network")
        print("  - Try specifying the network range manually")
        print("  - Verify port 80 is accessible (check firewall)")

if __name__ == "__main__":
    main()
