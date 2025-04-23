"""TCP server for handling concurrent connections and string queries.

This module implements a TCP server that binds to a configurable port, handles
unlimited concurrent connections using threading, receives strings in clear text
(up to 1024 bytes, stripping trailing \x00 characters), reads a file path from a
configuration file, searches for exact string matches in the file, responds with
'STRING EXISTS\n' or 'STRING NOT FOUND\n', and supports re-reading the file per query.
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
logger = logging.getLogger('StringSearchServer')

def parse_config(config_path: str = 'config.ini') -> Dict[str, str]:
    """Parse the configuration file into a dictionary.

    Reads the config file, extracting keys like 'port', 'linuxpath', and
    'REREAD_ON_QUERY', ignoring irrelevant elements.

    Args:
        config_path (str): Path to the configuration file. Defaults to 'config.ini'.

    Returns:
        Dict[str, str]: Dictionary containing configuration key-value pairs.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        ValueError: If 'linuxpath' or 'REREAD_ON_QUERY' is missing or malformed.
    """
    config = configparser.ConfigParser()
    if not config.read(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    result = {}
    for section in config:
        for key, value in config[section].items():
            if key.startswith('linuxpath'):
                if not value:
                    raise ValueError("linuxpath is empty in configuration file")
                result['linuxpath'] = value
            elif key.lower() == 'reread_on_query':
                if value.lower() not in ('true', 'false'):
                    raise ValueError("REREAD_ON_QUERY must be 'True' or 'False'")
                result['REREAD_ON_QUERY'] = value
            else:
                result[key] = value
    
    if 'linuxpath' not in result:
        raise ValueError("linuxpath not found in configuration file")
    if 'REREAD_ON_QUERY' not in result:
        raise ValueError("REREAD_ON_QUERY not found in configuration file")
    
    return result

class ServerConfig:
    """Represents the server configuration.

    Validates configuration settings, including the file path and re-read option,
    and loads the file into a set for fast lookups when not re-reading.

    Attributes:
        port (int): Port to bind the server to.
        linuxpath (Path): Path to the file for string searches.
        reread_on_query (bool): Whether to re-read the file for each query.
        file_lines (Set[str]): Set of lines from the file (if not re-reading).
    """
    def __init__(self, config_dict: Dict[str, str]):
        self.port = int(config_dict.get('port', 44445))
        self.linuxpath = config_dict.get('linuxpath')
        if self.linuxpath is None:
            raise ValueError("linuxpath not found in configuration file")
        self.linuxpath = Path(self.linuxpath)
        if not self.linuxpath.is_file():
            raise FileNotFoundError(f"File not found: {self.linuxpath}")
        self.reread_on_query = config_dict.get('REREAD_ON_QUERY').lower() == 'true'
        self.file_lines = self._load_file() if not self.reread_on_query else set()

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

    def search_file(self, query: str) -> bool:
        """Search for an exact string match in the file.

        Args:
            query (str): The string to search for.

        Returns:
            bool: True if the query matches a line in the file, False otherwise.
        """
        if self.reread_on_query:
            try:
                with open(self.linuxpath, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.rstrip('\n') == query:
                            return True
                return False
            except Exception as e:
                logger.error(f"Error reading file {self.linuxpath}: {e}")
                return False
        else:
            return query in self.file_lines

class MyTCPHandler(socketserver.BaseRequestHandler):
    """Handles individual client connections.

    Processes incoming TCP connections, receives strings in clear text (up to 1024 bytes,
    stripping trailing \x00 characters), searches for exact matches in the file, and
    responds with 'STRING EXISTS\n' or 'STRING NOT FOUND\n'.
    """
    def handle(self):
        """Process a single client request.

        Receives up to 1024 bytes, strips trailing \x00 characters, decodes as UTF-8,
        searches for the query in the file, logs the query and response, and sends
        the appropriate newline-terminated response.
        """
        try:
            # Receive data from the client (up to 1024 bytes)
            data = self.request.recv(1024)
            logger.debug(f"Received payload from {self.client_address[0]}: {len(data)} bytes")
            
            # Strip trailing \x00 characters
            stripped_data = data.rstrip(b'\x00')
            if len(data) != len(stripped_data):
                logger.debug(f"Stripped {len(data) - len(stripped_data)} \\x00 characters")
            
            # Decode the query
            query = stripped_data.decode('utf-8', errors='ignore')
            logger.debug(f"Decoded query from {self.client_address[0]}: '{query}'")
            
            # Search for exact match in the file
            server = self.server  # type: MyTCPServer
            response = ("STRING EXISTS\n" if server.config.search_file(query)
                        else "STRING NOT FOUND\n")
            
            # Log the response
            logger.debug(f"Sending response to {self.client_address[0]}: '{response}'")
            
            # Send response
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