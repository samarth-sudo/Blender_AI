"""
Executor Agent - Fifth agent in the pipeline.

Responsibility: Execute validated Blender Python code in headless Blender.

This agent:
1. Writes code to temporary script file
2. Runs Blender in background mode with the script
3. Captures stdout/stderr for debugging
4. Verifies .blend file was created
5. Returns execution results

This is where the actual simulation happens!
"""

import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional
from datetime import datetime

from src.agents.base_agent import BaseAgent
from src.models.schemas import BlenderCode, ExecutionResult
from src.utils.errors import ExecutionError, TimeoutError


class ExecutorAgent(BaseAgent):
    """
    Executor Agent: Run Blender Python code in headless mode.

    This agent executes validated code in a Blender subprocess.

    Key features:
    - Headless execution (no GUI)
    - Timeout protection
    - Output capture for debugging
    - .blend file verification

    Example:
        executor = ExecutorAgent()
        result = executor.run(
            code=validated_code,
            output_path="/tmp/simulation.blend"
        )
        if result.success:
            print(f"Simulation saved to: {result.blend_file_path}")
    """

    def __init__(self, blender_executable: Optional[str] = None, timeout: Optional[int] = None):
        """
        Initialize Executor Agent.

        Args:
            blender_executable: Path to Blender executable (defaults to config)
            timeout: Execution timeout in seconds (defaults to config)
        """
        super().__init__("ExecutorAgent")

        self.blender_executable = blender_executable or self.config.blender.executable
        self.timeout = timeout or self.config.blender.timeout_seconds

    def execute(
        self,
        code: BlenderCode,
        output_path: str,
        verbose: bool = False
    ) -> ExecutionResult:
        """
        Execute Blender Python code.

        Args:
            code: Validated BlenderCode object
            output_path: Where to save the .blend file
            verbose: If True, print Blender output in real-time

        Returns:
            ExecutionResult with success status and details

        Raises:
            ExecutionError: If Blender execution fails
            TimeoutError: If execution exceeds timeout
        """
        self.logger.info(
            f"Executing Blender script",
            output_path=output_path,
            timeout=self.timeout
        )

        start_time = datetime.now()

        # Create temporary script file
        script_path = self._write_temp_script(code.code)

        # Also save a copy for debugging
        debug_script = Path("/tmp/blender_debug_script.py")
        debug_script.write_text(code.code)
        self.logger.info(f"Debug script saved to: {debug_script}")

        try:
            # Run Blender
            stdout, stderr, returncode = self._run_blender(
                script_path,
                verbose=verbose
            )

            elapsed = (datetime.now() - start_time).total_seconds()

            # Check if execution succeeded
            if returncode != 0:
                raise ExecutionError(
                    f"Blender execution failed with exit code {returncode}",
                    blender_output=stderr,
                    exit_code=returncode
                )

            # Log Blender output for debugging
            self.logger.debug(f"Blender stdout:\n{stdout}")
            if stderr:
                self.logger.debug(f"Blender stderr:\n{stderr}")

            # Verify output file was created
            output_file = Path(output_path)
            if not output_file.exists():
                self.logger.error(
                    "execute",
                    Exception(f"File not created. Blender stdout:\n{stdout}\nstderr:\n{stderr}")
                )
                raise ExecutionError(
                    f"Blender completed but output file not found: {output_path}",
                    blender_output=stdout
                )

            # Get file size
            file_size = output_file.stat().st_size

            self.logger.success(
                "execute",
                output_path=output_path,
                file_size_mb=round(file_size / 1024 / 1024, 2),
                execution_time=elapsed
            )

            return ExecutionResult(
                success=True,
                blend_file_path=output_path,
                stdout=stdout,
                stderr=stderr,
                execution_time_seconds=elapsed,
                frame_count=self._extract_frame_count(stdout)
            )

        except subprocess.TimeoutExpired:
            elapsed = (datetime.now() - start_time).total_seconds()
            raise TimeoutError(
                f"Blender execution exceeded timeout of {self.timeout} seconds",
                timeout_seconds=self.timeout,
                operation="blender_execution"
            )

        except ExecutionError:
            raise

        except Exception as e:
            raise ExecutionError(
                f"Unexpected error during execution: {str(e)}",
                blender_output=str(e)
            )

        finally:
            # Clean up temp script
            try:
                script_path.unlink()
            except:
                pass

    def _write_temp_script(self, code: str) -> Path:
        """
        Write code to a temporary Python file.

        Args:
            code: Python code string

        Returns:
            Path to temporary file
        """
        # Create temp file in system temp directory
        fd, temp_path = tempfile.mkstemp(suffix=".py", prefix="blender_script_")

        try:
            with open(fd, 'w') as f:
                f.write(code)

            self.logger.debug(f"Created temp script: {temp_path}")
            return Path(temp_path)

        except Exception as e:
            raise ExecutionError(f"Failed to write temp script: {str(e)}")

    def _run_blender(
        self,
        script_path: Path,
        verbose: bool = False
    ) -> tuple[str, str, int]:
        """
        Run Blender in background mode with the script.

        Args:
            script_path: Path to Python script
            verbose: Print output in real-time

        Returns:
            Tuple of (stdout, stderr, returncode)

        Raises:
            TimeoutError: If execution times out
        """
        # Build Blender command
        # --background: Run without GUI
        # --factory-startup: Start with clean default scene (important for headless!)
        # --python: Execute Python script
        # --: Separator for script arguments
        cmd = [
            self.blender_executable,
            "--background",
            "--factory-startup",
            "--python", str(script_path),
            "--"
        ]

        self.logger.debug(f"Running command: {' '.join(cmd)}")

        try:
            # Run Blender process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait for completion with timeout
            stdout, stderr = process.communicate(timeout=self.timeout)

            if verbose:
                print("\n--- Blender Output ---")
                print(stdout)
                if stderr:
                    print("\n--- Blender Errors ---")
                    print(stderr)

            return stdout, stderr, process.returncode

        except subprocess.TimeoutExpired:
            # Kill the process
            process.kill()
            stdout, stderr = process.communicate()
            raise

        except FileNotFoundError:
            raise ExecutionError(
                f"Blender executable not found: {self.blender_executable}\n"
                f"Install Blender and ensure it's in PATH, or set BLENDER_EXECUTABLE env var.",
                blender_output="Blender not found"
            )

    def _extract_frame_count(self, stdout: str) -> int:
        """
        Extract frame count from Blender output.

        Args:
            stdout: Blender stdout

        Returns:
            Number of frames, or 0 if not found
        """
        # Look for patterns like "frames 1-250" or "frame_end=250"
        import re

        patterns = [
            r'frames (\d+)-(\d+)',
            r'frame_end=(\d+)',
            r'Saved:.*(\d+) frames',
        ]

        for pattern in patterns:
            match = re.search(pattern, stdout)
            if match:
                # Return the last number found (end frame)
                numbers = [int(g) for g in match.groups() if g.isdigit()]
                if numbers:
                    return max(numbers)

        return 0

    def check_blender_available(self) -> tuple[bool, str]:
        """
        Check if Blender is available and get version.

        Returns:
            Tuple of (is_available, version_or_error_message)
        """
        try:
            result = subprocess.run(
                [self.blender_executable, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                # Extract version from output
                version_line = result.stdout.split('\n')[0]
                return True, version_line

            return False, f"Blender command failed: {result.stderr}"

        except FileNotFoundError:
            return False, f"Blender not found at: {self.blender_executable}"

        except Exception as e:
            return False, f"Error checking Blender: {str(e)}"

    def dry_run(self, code: BlenderCode) -> tuple[bool, str]:
        """
        Perform a dry run to check if code would execute.

        This validates the Blender environment without actually running
        the simulation (which can be slow).

        Args:
            code: BlenderCode to test

        Returns:
            Tuple of (would_succeed, message)
        """
        # Check Blender is available
        blender_available, version = self.check_blender_available()

        if not blender_available:
            return False, version

        # Create a minimal test script
        test_script = """
import bpy
print("Blender Python API loaded successfully")
print(f"bpy.app.version: {bpy.app.version}")
"""

        script_path = self._write_temp_script(test_script)

        try:
            stdout, stderr, returncode = self._run_blender(script_path, verbose=False)

            if returncode == 0 and "loaded successfully" in stdout:
                return True, f"Blender ready: {version}"
            else:
                return False, f"Blender test failed: {stderr}"

        except Exception as e:
            return False, f"Dry run failed: {str(e)}"

        finally:
            try:
                script_path.unlink()
            except:
                pass

    def estimate_execution_time(self, code: BlenderCode) -> int:
        """
        Estimate how long execution will take.

        This is a rough estimate based on complexity score.

        Args:
            code: BlenderCode object

        Returns:
            Estimated seconds
        """
        if code.estimated_execution_time:
            return code.estimated_execution_time

        # Fallback based on complexity
        base_time = 30  # Base overhead
        complexity_time = code.complexity_score * 120  # Up to 2 minutes for complex sims

        return int(base_time + complexity_time)
