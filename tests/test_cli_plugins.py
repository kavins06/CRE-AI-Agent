from types import ModuleType

import pytest
import typer
from typer.testing import CliRunner


def plugin(name: str, command: str) -> ModuleType:
    module = ModuleType(name)

    def register_cli(app: typer.Typer) -> None:
        @app.command(command)
        def execute() -> None:
            typer.echo("registered")

    module.register_cli = register_cli
    return module


def test_t001_ac5_plugin_commands_reach_real_typer_dispatch() -> None:
    from cre_brain.cli import create_app

    app = create_app(plugins=[plugin("cre_brain.release.cli_release", "build")])
    result = CliRunner().invoke(app, ["build"])
    assert result.exit_code == 0
    assert result.output.strip() == "registered"


def test_t001_ac5_plugin_discovery_uses_installed_package_not_cwd(
    tmp_path,
    monkeypatch,
) -> None:
    from cre_brain.cli import discover_plugins

    (tmp_path / "cli_untrusted.py").write_text("raise RuntimeError('untrusted')\n")
    monkeypatch.chdir(tmp_path)
    assert list(discover_plugins()) == []


@pytest.mark.parametrize("name", ["cli", "cre_brainx.cli", "outside.cli"])
def test_t001_ac5_plugin_rejects_outside_package(name: str) -> None:
    from cre_brain.cli import create_app

    with pytest.raises(ValueError, match="cre_brain"):
        create_app(plugins=[plugin(name, "outside")])


def test_t001_ac5_plugin_invalid_registration_fails_closed() -> None:
    from cre_brain.cli import create_app

    with pytest.raises(ValueError, match="register_cli"):
        create_app(plugins=[ModuleType("cre_brain.release.cli_bad")])


def test_t001_ac5_plugin_duplicate_command_fails_closed() -> None:
    from cre_brain.cli import create_app

    with pytest.raises(ValueError, match="Duplicate CLI command"):
        create_app(
            plugins=[
                plugin("cre_brain.release.cli_one", "same"),
                plugin("cre_brain.runner.cli_two", "same"),
            ]
        )


def test_t001_ac5_plugin_failure_is_not_silently_ignored() -> None:
    from cre_brain.cli import create_app

    module = ModuleType("cre_brain.release.cli_failure")

    def register_cli(app: typer.Typer) -> None:
        raise RuntimeError("configuration invalid")

    module.register_cli = register_cli
    with pytest.raises(RuntimeError, match="configuration invalid"):
        create_app(plugins=[module])


def test_t001_ac5_nested_plugin_group_dispatch_and_duplicate_rejection() -> None:
    from cre_brain.cli import create_app

    module = ModuleType("cre_brain.release.cli_group")
    group = typer.Typer()

    @group.command()
    def build() -> None:
        typer.echo("release built")

    def register_cli(app: typer.Typer) -> None:
        app.add_typer(group, name="release")

    module.register_cli = register_cli
    result = CliRunner().invoke(create_app(plugins=[module]), ["release", "build"])
    assert result.exit_code == 0
    assert result.output.strip() == "release built"

    group.command("build")(lambda: None)
    with pytest.raises(ValueError, match="Duplicate CLI command"):
        create_app(plugins=[module])


def test_t001_ac5_plugin_cannot_overwrite_global_version_callback() -> None:
    from cre_brain.cli import create_app

    module = ModuleType("cre_brain.runner.cli_invalid")

    def register_cli(app: typer.Typer) -> None:
        app.callback()(lambda: None)

    module.register_cli = register_cli
    with pytest.raises(ValueError, match="root callback"):
        create_app(plugins=[module])
