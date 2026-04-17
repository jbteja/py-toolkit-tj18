#!/usr/bin/env python

import shutil
import subprocess
import sys
from pathlib import Path

import yaml

# Parent directory to sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.logger import get_logger

logger = get_logger(__name__)


def check_binary(bin_path):
    """
    Checks if a given binary is available in the system PATH.

    Args:
        bin_path (str): The name or path of the executable to check.

    Raises:
        SystemExit: If the binary is not found.
    """
    try:
        if shutil.which(bin_path) is None:
            raise FileNotFoundError(f"Binary not found: {bin_path}")

        logger.info("Binary verified and available: %s", bin_path)

    except FileNotFoundError as e:
        logger.warning("Configuration Error: %s", e)
        logger.error(
            "Please ensure the application is installed and accessible in your system PATH"
        )
        sys.exit(1)

    except Exception as e:
        logger.exception(
            "An unexpected error occurred while checking for %s: %s", bin_path, e
        )
        sys.exit(1)


def run_command(cmd, description):
    """
    Helper to execute command-line.

    Args:
        cmd (list): The command to run, formatted as a list of strings.
        description (str): A description of the task being performed.

    Raises:
        subprocess.CalledProcessError: If the command fails to execute.
    """
    logger.info("Starting task: %s", description)

    try:
        # shell=False is used for security to prevent shell injection
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info("Completed: %s", description)

    except subprocess.CalledProcessError as e:
        logger.warning("Failed: %s", description)
        logger.debug("Command executed: %s", " ".join(cmd))
        logger.debug("Return code: %d", e.returncode)

        if e.stderr:
            # We look for lines containing 'HTTP' or 'Server returned'
            error_lines = e.stderr.strip().splitlines()
            relevant_errors = [
                line.strip()
                for line in error_lines
                if "HTTP" in line or "Server returned" in line
            ]

            if relevant_errors:
                # Join the filtered lines with a newline for the log
                logger.error("Errors found:\n%s", "\n".join(relevant_errors))

            else:
                # Fallback: if no HTTP error found, show the last 3 lines
                logger.error("Error output:\n%s", "\n".join(error_lines[-3:]))
        raise

    except Exception:
        logger.exception("An unexpected error occurred during: %s", description)
        raise


def process_video_library(config, out_dir, bin_path):
    """
    Iterates through the video library and processes each entry based on
    transcoding settings.
    """
    transcoding_cfg = config.get("transcoding", {})
    capture_raw = transcoding_cfg.get("capture_raw", False)

    for title, url in config.get("videos", {}).items():
        # --- Path Setup ---
        if capture_raw:
            # Per instructions: raw capture ignores settings and uses .ts
            extension = ".ts"
            description = f"Capturing raw stream for '{title}'"

        else:
            extension = transcoding_cfg.get("extension", ".mp4")
            description = f"Transcoding '{title}' to {extension}"

        # Clean title to ensure it's a valid filename and build path
        safe_title = "".join(x for x in title if x.isalnum() or x in "._- ")
        output_file = out_dir / f"{safe_title}{extension}"

        # --- Command Construction ---
        if capture_raw:
            # Generic stream copy: -c copy handles both audio and video
            cmd = [bin_path, "-y", "-i", url, "-c", "copy", str(output_file)]

        else:
            # Detailed transcoding using config settings
            v_codec = transcoding_cfg.get("video_codec", "libx264")
            a_codec = transcoding_cfg.get("audio_codec", "copy")
            crf = str(transcoding_cfg.get("crf_value", 23))

            cmd = [
                bin_path,
                "-y",
                "-i",
                url,
                "-c:v",
                v_codec,
                "-crf",
                crf,
                "-c:a",
                a_codec,
                str(output_file),
            ]

        # --- Execution ---
        try:
            # Using the generic runner function from the previous step
            run_command(cmd, description)
            logger.debug("Successfully processed video: %s", title)

        except Exception:
            logger.warning("Skipping '%s' due to processing error.", title)
            continue


def main():
    # Load configuration
    try:
        with open("config.yaml") as f:
            config = yaml.safe_load(f)

    except FileNotFoundError:
        logger.error("Configuration file 'config.yaml' not found")
        sys.exit(1)

    except yaml.YAMLError as e:
        logger.error("Error parsing config.yaml: %s", e)
        sys.exit(1)

    # Validate binary path from config
    bin_path = config.get("paths", {}).get("bin_path")
    if bin_path:
        check_binary(bin_path)

    else:
        logger.error("Config Error: 'paths.bin_path' is missing from config.yaml.")
        sys.exit(1)

    # Validate output directory from config
    out_dir_path = config.get("paths", {}).get("output_directory", "../downloads")
    out_dir = Path(out_dir_path)

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Output directory is ready: %s", out_dir.resolve())

    except OSError as e:
        logger.error("Failed to create output directory '%s': %s", out_dir, e)
        sys.exit(1)

    # Process the video library based on the loaded configuration
    process_video_library(config, out_dir, bin_path)


if __name__ == "__main__":
    main()
