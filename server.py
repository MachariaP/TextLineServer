#!/usr/bin/env python3

import socketserver
import configparser
from typing import Dict

def parse_config(config_path: str = 'config.ini') -> Dict[str, str]:
    """Parse the configuration file into a dictionary."""
    config = configparser.ConfigParser()
    config.read(config_path)
    return dict(config['SERVER']) # Assumig settings are under [SERVER] section

class MyTCPHandler(socketserver.BaseRequestHandler):
    """Handles individual client connections."""
    def handle(self):
        """Process a single client request."""
        try:
            # Receive data from the client
            data = self.request.recv(1024).strip()
            print(f"Received from {self.client_address}: {data.decode('utf-8', errors='ignore')}")

            # Send a response back to the client
            response = "Hello, client!"
            self.request.sendall(response.encode('utf-8'))
        except Exception as e:
            print(f"Error handling client {self.client_address}: {e}")

def main():
    # Load configuration
    config_dict = parse_config()
    port = int(config_dict.get('port', 44445))

    # Create and start the server
    host = '127.0.0.1'  # Bind to localhost
    with socketserver.ThreadingTCPServer((host, port), MyTCPHandler) as server:
        print(f"Server listening on {host}:{port}")
        server.serve_forever()

if __name__ == "__main__":
    main()
