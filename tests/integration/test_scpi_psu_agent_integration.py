import pytest

import ocs
from ocs.base import OpCode

from ocs.testing import (
    create_agent_runner_fixture,
    create_client_fixture,
)

from integration.util import create_crossbar_fixture

from socs.testing.device_emulator import create_device_emulator

pytest_plugins = "docker_compose"

wait_for_crossbar = create_crossbar_fixture()
run_agent = create_agent_runner_fixture(
    "../agents/scpi_psu/scpi_psu_agent.py",
    "scpi_psu_agent",
    args=["--log-dir", "./logs/"],
)
client = create_client_fixture("psuK")
gpib_emu = create_device_emulator({"SYST:REM": ""}, relay_type="tcp")


@pytest.mark.integtest
def test_testing(wait_for_crossbar):
    """Just a quick test to make sure we can bring up crossbar."""
    assert True


@pytest.mark.integtest
def test_scpi_psu_set_output(wait_for_crossbar, gpib_emu, run_agent, client):
    client.init()
    resp = client.set_output(channel=3, state=True)
    print(resp)
    assert resp.status == ocs.OK
    print(resp.session)
    assert resp.session["op_code"] == OpCode.SUCCEEDED.value
