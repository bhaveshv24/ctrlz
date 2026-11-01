from ctrlz import runtime


def test_execution_requires_real_daemon_not_only_enabled_flag(monkeypatch):
    monkeypatch.setattr(runtime, 'command_status', lambda args: {'state':'unavailable'})
    assert not runtime.execution_readiness(True)['available']
    assert 'Docker' in runtime.execution_readiness(True)['reason']
    monkeypatch.setattr(runtime, 'command_status', lambda args: {'state':'available'})
    assert runtime.execution_readiness(True)['available']
    assert not runtime.execution_readiness(False)['available']
