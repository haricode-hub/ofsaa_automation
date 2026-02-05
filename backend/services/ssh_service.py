import asyncio
import logging
from typing import Dict, Any
import paramiko
from paramiko.ssh_exception import AuthenticationException, SSHException, NoValidConnectionsError
import socket
import threading
import time

logger = logging.getLogger(__name__)

class SSHService:
    """Service for handling SSH connections and command execution using paramiko"""
    
    def __init__(self):
        self.connection_timeout = 30
        self.command_timeout = 600  # 10 minutes for command execution
    
    async def test_connection(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """Test SSH connection to the target host"""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._test_connection_sync, host, username, password
            )
            return result
        except Exception as e:
            logger.error(f"SSH connection test failed: {str(e)}")
            return {
                "success": False,
                "error": f"Connection test failed: {str(e)}"
            }
    
    def _test_connection_sync(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """Synchronous SSH connection test"""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            logger.info(f"🔗 Attempting SSH connection to {host}:22 as {username}")
            print(f"🔗 SSH Debug: Testing connection to {host} with user '{username}'")
            
            # Try connecting with different approaches
            connection_attempts = [
                # Attempt 1: Standard connection
                {
                    "hostname": host,
                    "username": username,
                    "password": password,
                    "timeout": self.connection_timeout,
                    "auth_timeout": self.connection_timeout,
                    "look_for_keys": False,
                    "allow_agent": False,
                    "port": 22,
                    "banner_timeout": 30,
                    "disabled_algorithms": {"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]}
                },
                # Attempt 2: With different algorithms
                {
                    "hostname": host,
                    "username": username,
                    "password": password,
                    "timeout": self.connection_timeout,
                    "auth_timeout": self.connection_timeout,
                    "look_for_keys": False,
                    "allow_agent": False,
                    "port": 22,
                    "banner_timeout": 60
                }
            ]
            
            for i, params in enumerate(connection_attempts, 1):
                try:
                    print(f" Connection attempt {i}/2...")
                    client.connect(**params)
                    print(f" Connection attempt {i} successful!")
                    break
                except Exception as attempt_error:
                    print(f" Connection attempt {i} failed: {str(attempt_error)}")
                    if i == len(connection_attempts):
                        raise attempt_error
                    client.close()
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            logger.info(f"SSH connection established to {host}")
            
            # Test with a simple command
            stdin, stdout, stderr = client.exec_command("echo 'Connection successful'", timeout=30)
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            exit_status = stdout.channel.recv_exit_status()
            
            client.close()
            
            if exit_status == 0:
                logger.info(f"SSH test command successful on {host}")
                return {
                    "success": True,
                    "message": "SSH connection successful",
                    "output": output
                }
            else:
                logger.error(f"SSH test command failed on {host}: {error}")
                return {
                    "success": False,
                    "error": f"Test command failed: {error}",
                    "returncode": exit_status
                }
                
        except AuthenticationException as e:
            logger.error(f"SSH authentication failed for {username}@{host}: {str(e)}")
            print(f" Authentication Error: {str(e)}")
            print(f"Possible causes:")
            print(f"   - Wrong username (try 'oracle' instead of 'Oracle')")
            print(f"   - Wrong password") 
            print(f"   - Account locked/disabled")
            print(f"   - SSH server configuration restricts this user")
            return {
                "success": False,
                "error": "Authentication failed - check username/password"
            }
        except paramiko.SSHException as e:
            if "Connection lost" in str(e) or "Server connection dropped" in str(e):
                logger.error(f"SSH connection dropped by server {host}: {str(e)}")
                print(f" Connection dropped by server: {str(e)}")
                print(f" This usually means:")
                print(f"   - Server security policy rejected the connection")
                print(f"   - Account is disabled or restricted")
                print(f"   - SSH server configuration issue")
                return {
                    "success": False,
                    "error": "Connection dropped by server - check account permissions"
                }
            else:
                logger.error(f"SSH protocol error with {host}: {str(e)}")
                print(f" SSH Protocol Error: {str(e)}")
                return {
                    "success": False,
                    "error": f"SSH error: {str(e)}"
                }
        except NoValidConnectionsError as e:
            logger.error(f"SSH connection refused to {host}: {str(e)}")
            return {
                "success": False,
                "error": f"Connection refused - check if SSH service is running on {host}:22"
            }
        except socket.timeout as e:
            logger.error(f"SSH connection timeout to {host}: {str(e)}")
            return {
                "success": False,
                "error": f"Connection timed out - check host {host} is reachable"
            }
        except socket.gaierror as e:
            logger.error(f"DNS resolution failed for {host}: {str(e)}")
            return {
                "success": False,
                "error": f"Cannot resolve hostname {host} - check the address"
            }
        except ConnectionRefusedError as e:
            logger.error(f"Connection refused to {host}:22: {str(e)}")
            return {
                "success": False,
                "error": f"Connection refused - SSH service may not be running on {host}"
            }
        except SSHException as e:
            logger.error(f"SSH protocol error with {host}: {str(e)}")
            return {
                "success": False,
                "error": f"SSH error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error connecting to {host}: {str(e)}")
            return {
                "success": False,
                "error": f"Connection failed: {str(e)}"
            }
        finally:
            try:
                client.close()
            except:
                pass
    
    async def execute_command(self, host: str, username: str, password: str, command: str, timeout: int = None) -> Dict[str, Any]:
        """Execute a command on the remote host via SSH with optional custom timeout"""
        try:
            logger.info(f"Executing SSH command on {host}: {command}")
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._execute_command_sync, host, username, password, command, timeout
            )
            return result
        except Exception as e:
            logger.error(f"SSH command execution failed: {str(e)}")
            return {
                "success": False,
                "error": f"Command execution failed: {str(e)}",
                "command": command
            }
    
    def _execute_command_sync(self, host: str, username: str, password: str, command: str, timeout: int = None) -> Dict[str, Any]:
        """Synchronous SSH command execution with optional custom timeout"""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Use custom timeout or default
        cmd_timeout = timeout if timeout is not None else self.command_timeout
        
        try:
            # Connect
            client.connect(
                hostname=host,
                username=username,
                password=password,
                timeout=self.connection_timeout,
                auth_timeout=self.connection_timeout,
                look_for_keys=False,
                allow_agent=False
            )
            
            # Execute command with timeout
            stdin, stdout, stderr = client.exec_command(command, timeout=cmd_timeout)
            
            # Read output with timeout
            stdout_data = self._read_with_timeout(stdout, cmd_timeout)
            stderr_data = self._read_with_timeout(stderr, cmd_timeout)
            
            exit_status = stdout.channel.recv_exit_status()
            
            client.close()
            
            return {
                "success": exit_status == 0,
                "stdout": stdout_data,
                "stderr": stderr_data,
                "returncode": exit_status,
                "command": command
            }
            
        except AuthenticationException:
            return {
                "success": False,
                "error": "Authentication failed - check username/password",
                "command": command,
                "returncode": -1,
                "stdout": "",
                "stderr": "Authentication failed"
            }
        except socket.timeout:
            return {
                "success": False,
                "error": f"Command timed out after {cmd_timeout} seconds",
                "command": command,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {self.command_timeout} seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Command execution failed: {str(e)}",
                "command": command,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e)
            }
        finally:
            try:
                client.close()
            except:
                pass
    
    def _read_with_timeout(self, stream, timeout: int) -> str:
        """Read from stream with timeout"""
        start_time = time.time()
        data = []
        
        while True:
            if time.time() - start_time > timeout:
                raise socket.timeout(f"Read timeout after {timeout} seconds")
            
            if stream.channel.recv_ready():
                chunk = stream.read(4096)
                if not chunk:
                    break
                data.append(chunk)
            elif stream.channel.exit_status_ready():
                # Command finished, read any remaining data
                remaining = stream.read()
                if remaining:
                    data.append(remaining)
                break
            else:
                time.sleep(0.1)
        
        return b''.join(data).decode('utf-8', errors='replace').strip()
    
    async def execute_interactive_command(
        self, 
        host: str, 
        username: str, 
        password: str, 
        command: str,
        on_output_callback = None,
        on_prompt_callback = None,
        timeout: int = 1800  # 30 minutes default for interactive scripts
    ) -> Dict[str, Any]:
        """
        Execute command interactively, streaming output and handling input prompts
        
        Args:
            host: Target hostname
            username: SSH username
            password: SSH password
            command: Command to execute
            on_output_callback: Async callback for streaming output lines
            on_prompt_callback: Async callback for handling prompts (returns user input)
            timeout: Command timeout in seconds
            
        Returns:
            Dict with success, output, and exit code
        """
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, 
                self._execute_interactive_command_sync,
                host, username, password, command, on_output_callback, on_prompt_callback, timeout
            )
            return result
        except Exception as e:
            logger.error(f"Interactive command execution failed: {str(e)}")
            return {
                "success": False,
                "error": f"Interactive command failed: {str(e)}",
                "command": command
            }
    
    def _execute_interactive_command_sync(
        self, 
        host: str, 
        username: str, 
        password: str, 
        command: str,
        on_output_callback,
        on_prompt_callback,
        timeout: int
    ) -> Dict[str, Any]:
        """Synchronous interactive command execution"""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # Connect
            client.connect(
                hostname=host,
                username=username,
                password=password,
                timeout=self.connection_timeout,
                auth_timeout=self.connection_timeout,
                look_for_keys=False,
                allow_agent=False
            )
            
            # Get interactive shell channel
            channel = client.invoke_shell()
            channel.settimeout(0.5)  # Non-blocking reads
            
            all_output = []
            current_line = ""
            
            # Send command
            channel.send(command + '\n')
            
            start_time = time.time()
            prompt_patterns = [
                'Enter', 'enter', 'Input', 'input', 'Type', 'type',
                '[Y/n]', '[y/N]', 'Continue?', 'Proceed?', 'password:', 'Password:'
            ]
            
            while True:
                # Check timeout
                if time.time() - start_time > timeout:
                    logger.warning(f"Interactive command timed out after {timeout}s")
                    break
                
                # Check if command finished
                if channel.exit_status_ready():
                    # Read remaining output
                    while channel.recv_ready():
                        chunk = channel.recv(4096).decode('utf-8', errors='replace')
                        all_output.append(chunk)
                        if on_output_callback:
                            asyncio.run(on_output_callback(chunk))
                    break
                
                # Read available output
                try:
                    if channel.recv_ready():
                        chunk = channel.recv(4096).decode('utf-8', errors='replace')
                        all_output.append(chunk)
                        current_line += chunk
                        
                        # Stream output
                        if on_output_callback:
                            asyncio.run(on_output_callback(chunk))
                        
                        # Check for prompts
                        if on_prompt_callback and any(pattern in current_line for pattern in prompt_patterns):
                            # Detected potential prompt
                            logger.info(f"Potential prompt detected: {current_line[-100:]}")
                            user_input = asyncio.run(on_prompt_callback(current_line))
                            
                            if user_input:
                                channel.send(user_input + '\n')
                                current_line = ""  # Reset line buffer
                        
                        # Reset line buffer on newline
                        if '\n' in chunk:
                            current_line = ""
                            
                except socket.timeout:
                    # No data available, continue
                    time.sleep(0.1)
                    continue
            
            exit_code = channel.recv_exit_status()
            channel.close()
            client.close()
            
            full_output = ''.join(all_output)
            
            return {
                "success": exit_code == 0,
                "output": full_output,
                "returncode": exit_code,
                "command": command
            }
            
        except Exception as e:
            logger.error(f"Interactive command execution error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "command": command,
                "returncode": -1
            }
        finally:
            try:
                client.close()
            except:
                pass