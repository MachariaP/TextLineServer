#!/usr/bin/env python3
"""TCP client for querying the TextLineServer interactively.

This module implements a client that connects to the TextLineServer, allows users to
enter string queries interactively (up to 1024 bytes including newline), and receives
responses indicating whether the string exists in the server's file. Exits gracefully on Ctrl+C.
"""

import socket
import argparse
import logging
from typing import Tuple

# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler()  # Console output
    ]
)
logger = logging.getLogger('TextLineClient')

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments containing host and port.
    """
    parser = argparse.ArgumentParser(description="Interactively query the TextLineServer.")
    parser.add_argument(
        '--host', type=str, default='127.0.0.1',
        help='Server host (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port', type=int, default=44445,
        help='Server port (default: 44445)'
    )
    return parser.parse_args()

def create_connection(host: str, port: int) -> socket.socket:
    """Create and connect a TCP socket to the server.
    
    Args:
        host (str): Server host address.
        port (int): Server port number.
    
    Returns:
        socket.socket: Connected socket object.
    
    Raises:
        ConnectionRefusedError: If connection to the server fails.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect((host, port))
        logger.info(f"Connected to {host}:{port}")
        return s
    except ConnectionError as e:
        logger.error(f"Failed to connect to {host}:{port}: {e}")
        raise

def query_server(sock: socket.socket, query: str) -> str:
    """Send a query to the server and return the response.
    
    Args:
        sock (socket.socket): Connected socket to the server.
        query (str): Query string to send to the server.
    
    Returns:
        str: Response from the server ('STRING EXISTS' or 'STRING NOT FOUND').

    Raises:
        socket.error: If communication with the server fails.
        valueError: If the query exceeds 1024 bytes after encoding.
    """
    try:
        # Validate payload size (including newline)
        encoded_query = f"{query}\n".encode('utf-8')
        if len(encoded_query) > 1024:
            raise ValueError("Query exceeds 1024 bytes: {len(encoded_query)} bytes")

        # Send the query to the server
        sock.sendall(encoded_query)
        logger.debug(f"Sent query: '{query}' ({len(encoded_query)} bytes)")

        # Receive the response from the server (up to 1024 bytes)
        response = sock.recv(1024).decode('utf-8', errors='ignore').strip()
        logger.debug(f"Received response: '{response}'")
        return response
    except socket.error as e:
        logger.error(f"Error communicating with server: {e}")
        raise

def main():
    """Run the client interactively, allowing multiple queries untill Ctrl+C is pressed."""
    try:
        args = parse_args()
        # Create initial connection to the server
        sock = create_connection(args.host, args.port)

        print("Enter a query string (Ctrl+C to exit):")
        while True:
            try:
                # Prompt for query
                query = input("> ").strip()
                if not query:
                    print("Empty query, please enter a valid string.")
                    continue

                try:
                    # Send query and receive response
                    response = query_server(sock, query)
                    print(f"Server response: {response}")
                except socket.error:
                    # Reconnect if communication fails
                    logger.info("Connection lost, attempting to reconnect...")
                    sock.close()
                    sock = create_connection(args.host, args.port)
                    # Retry the query
                    response = query_server(sock, query)
                    print(f"Server response: {response}")

            except socket.error as e:
                logger.error(f"Failed to recover connection: {e}")
                sock.close()
                break
            except ValueError as e:
                print(f"Error: {e}")
                continue

    except KeyboardInterrupt:
        logger.info("Received Ctrl+C, shutting down...")
    except Exception as e:
        logger.error(f"Client failed: {e}")
        raise
    finally:
        if sock is not None:
            sock.close()
            logger.info("Connection closed.")


if __name__ == "__main__":
    main()