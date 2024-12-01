#################################################################################
# PRIMO - The P&A Project Optimizer was produced under the Methane Emissions
# Reduction Program (MERP) and National Energy Technology Laboratory's (NETL)
# National Emissions Reduction Initiative (NEMRI).
#
# NOTICE. This Software was developed under funding from the U.S. Government
# and the U.S. Government consequently retains certain rights. As such, the
# U.S. Government has been granted for itself and others acting on its behalf
# a paid-up, nonexclusive, irrevocable, worldwide license in the Software to
# reproduce, distribute copies to the public, prepare derivative works, and
# perform publicly and display publicly, and to permit others to do so.
#################################################################################


# Standard libs
import logging

# Installed libs
import pytest

# User-defined libs
from primo.utils.setup_logger import setup_logger


def test_no_logs(caplog):
    """
    Test where no logs are captured
    """
    setup_logger(0, False)
    logger = logging.getLogger("test_setup_logger")
    logger.info("This will not be captured")
    assert caplog.text == ""

    # Warning logs are always captured
    logger.warning("This will be captured")
    assert (
        caplog.text
        == "WARNING  test_setup_logger:test_setup_logger.py:35 This will be captured\n"
    )


def test_logs(caplog, tmp_path):
    """
    Tests where logs are captured both in stdout and on disk
    """
    with caplog.at_level(logging.INFO):
        setup_logger(2, True)
        logger = logging.getLogger("test_setup_logger")

        logger.info("This will be captured on stdout")

        msg = (
            "INFO     test_setup_logger:test_setup_logger.py:50 "
            "This will be captured on stdout\n"
        )
        assert caplog.text == msg

    log_file = tmp_path / "log.txt"
    setup_logger(2, True, log_file)

    with pytest.raises(ValueError) as exc_info:
        setup_logger(2, True, log_file)

    assert (
        str(exc_info.value)
        == f"Log file: {str(log_file)} already exists. Please specify new log file."
    )
