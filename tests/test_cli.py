from deptagents import cli


def test_departments_lists_tools(capsys, monkeypatch):
    monkeypatch.delenv("DEPTAGENTS_STATE", raising=False)
    assert cli.main(["departments"]) == 0
    out = capsys.readouterr().out
    for name in ["hr:", "finance:", "it:", "request_leave", "submit_expense", "open_ticket"]:
        assert name in out


def test_ask_without_credentials_exits_2(capsys, monkeypatch):
    for var in ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"]:
        monkeypatch.delenv(var, raising=False)
    import anthropic
    from deptagents import agent

    class NoAuth:
        def __init__(self, *a, **k):
            raise anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)

    monkeypatch.setattr(agent.anthropic, "Anthropic", NoAuth)
    code = cli.main(["ask", "hello"])
    assert code == 2
    assert "credentials" in capsys.readouterr().err


def test_ask_with_no_credentials_at_all_exits_2(capsys, monkeypatch):
    """The real SDK raises TypeError at the first request when nothing is configured."""
    for var in ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", "/nonexistent")  # no `ant auth login` profile on disk
    code = cli.main(["ask", "hello", "--department", "it"])
    assert code == 2
    assert "credentials" in capsys.readouterr().err
