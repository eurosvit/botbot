import socket
import psutil

def find_process_using_port(port):
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        for conn in proc.connections(kind="inet"):
            if conn.laddr.port == port:
                return proc.info
    return None

port = 10000
process_info = find_process_using_port(port)

if process_info:
    print(f"Port {port} is in use by process: {process_info['name']} (PID: {process_info['pid']})")
else:
    print(f"Port {port} is free.")
