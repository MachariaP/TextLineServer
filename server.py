#!/usr/bin/env python3

"""
TCP server for handling concurrent connections and string queries.

This module implements a TCP server that binds to a configurable port, handles
unlimited concurrent connections using threading, and receives strings in clear text,
reads a file path from a configuration file, and searches for exact string matches
in the file, responding with 'STRING EXISTS' or 'STRING NOT FOUND'.
"""

import socketserver
import configparser
import logging
from typing import Dict, Set
from pathlib import Path

# Configure logging to output to console and file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler('server.log')  # File output
    ]
)
logger = logging.getLogger('stringsearchserver')

def parse_config(config_path: str = 'config.ini') -> Dict[str, str]:
    """Parse the configuration file into a dictionary.

    Reads the config file, extracting keys like 'port' and 'linuxpath', ignoring
    irrelevant elements. Ensures 'linuxpath' is present in the expected format.

    Args:
        config_path(str): Path to the configuration file. Defaults to 'config.ini'.

    Returns:
        Dict[str, str]: Dictionary containing configuration key-value pairs.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        ValueError: If 'linuxpath' is missing or malformed.
    """
    config = configparser.ConfigParser()
    if not config.read(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    # Flatten the config into a single dictionary
    result = {}
    for section in config:
        for key, value in config[section].items():
            if key.startswith('linuxpath'):
                if not value:
                    raise ValueError("linuxpath is empty in configuration file")
                result['linuxpath'] = value
            else:
                result[key] = value

    if 'linuxpath' not in result:
        raise ValueError("linuxpath not found in configuration file")
    
    return result


class ServerConfig:
    """Represents the server configuration.

    Validates configuration settings, including the file path for string searches,
    and loads the file into a set for fast lookups.

    Attributes:
        port (int): Port to bind the server to.
        linuxpath (Path): Path to the file for string searches.
        file_lines (Set[str]): Set of lines from the file for exact matching.
    """
    def __init__(self, config_dict: Dict[str, str]):
        self.port = int(config_dict.get('port', 44445))
        self.linuxpath = config_dict.get('linuxpath')
        if self.linuxpath is None:
            raise ValueError("linuxpath not found in configuration file")
        self.linuxpath = Path(self.linuxpath)

        # Validate that the file exists
        if not self.linuxpath.is_file():
            raise FileNotFoundError(f"File not found: {self.linuxpath}")
        
        # Load the file into a set for fast lookups
        self.file_lines = self._load_file()

    def _load_file(self) -> Set[str]:
        """Load the file into a set of lines, stripping newlines.

        Returns:
            Set[str]: Set containing each line from the file.
        """
        try:
            with open(self.linuxpath, 'r', encoding='utf-8') as f:
                return {line.rstrip('\n') for line in f if line.strip()}
        except Exception as e:
            logger.error(f"Failed to load file {self.linuxpath}: {e}")
            raise

class MyTCPHandler(socketserver.BaseRequestHandler):
    """Handles individual client connections.

    Process incoming TCP connections, receives strings in clear text, logs queries,
    and sends placeholder responses until search functionality is implemented.
    """
    def handle(self):
        """Process a single client request.

        Receive up to 1024 bytes, strips trailing null characters, decodes as UTF-8,
        logs the query with client IP, and sends a placeholder response.
        """
        try:
            # Receive data from the client (up to 1024 bytes)
            data = self.request.recv(1024).rstrip(b'\x00')
            query = data.decode('utf-8', errors='ignore')

            # Log the received query with IP and timestamp
            logger.debug(f"Received query from {self.client_address[0]}: {query}")

            # Search for exact match in the file
            server = self.server  # type: MyTCPServer
            response = ("STRING EXISTS\n" if query in server.config.file_lines
                       else "STRING NOT FOUND\n")
            
            # Send the response back to the client
            self.request.sendall(response.encode('utf-8'))
        except Exception as e:
            logger.error(f"Error handling client {self.client_address}: {e}")


class MyTCPServer(socketserver.ThreadingTCPServer):
    """Custom TCP server with threading for concurrent connections.

    Stores configuration for access by request handlers.
    """
    def __init__(self, server_address, RequestHandlerClass, config):
        super().__init__(server_address, RequestHandlerClass)
        self.config = config

def main():
    """Start the TCP server with configuration from config.ini.

    Loads configuration, initializes the server, and runs it indefinitely to handle
    concurrent client connections.
    """
    try:
        # Load configuration
        config_dict = parse_config()
        config = ServerConfig(config_dict)

        # Create and start the server
        host = '127.0.0.1'  # Bind to localhost
        with MyTCPServer((host, config.port), MyTCPHandler, config) as server:
            logger.info(f"Server listening on {host}:{config.port}")
            server.serve_forever()
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        raise

if __name__ == "__main__":
    main()
