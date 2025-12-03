from pathlib import Path
import shutil
import sys

from lsprotocol import types as lsp
import pytest
import pytest_lsp

MY_DIR = Path(__file__).parent.resolve()
LSP_BIN = MY_DIR / ".." / "src" / "tclint" / "cli" / "tclsp.py"


def get_capabilities(client: str) -> lsp.ClientCapabilities:
    capabilities = pytest_lsp.client_capabilities(client)
    # Need to nullify these capabilities, since pytest_lsp doesn't support them
    try:
        capabilities.workspace.diagnostics.refresh_support = False
    except AttributeError:
        pass
    try:
        capabilities.workspace.did_change_watched_files.dynamic_registration = False
    except AttributeError:
        pass
    return capabilities


@pytest_lsp.fixture(
    config=pytest_lsp.ClientServerConfig(
        # -I ensures the server imports the tclint package instead of the entry point.
        server_command=[sys.executable, "-I", str(LSP_BIN)]
    )
)
async def client(lsp_client: pytest_lsp.LanguageClient, request):
    yield

    # Teardown
    await lsp_client.shutdown_session()


@pytest.mark.asyncio
async def test_diagnostics(client: pytest_lsp.LanguageClient):
    """Basic diagnostics test."""
    params = lsp.InitializeParams(capabilities=get_capabilities("visual-studio-code"))
    await client.initialize_session(params)

    document = MY_DIR / "data" / "dirty.tcl"
    results = await client.text_document_diagnostic_async(
        params=lsp.DocumentDiagnosticParams(
            text_document=lsp.TextDocumentIdentifier(uri=f"file://{document}")
        )
    )
    assert results is not None
    assert len(results.items) == 2
    items = sorted(
        results.items, key=lambda r: (r.range.start.line, r.range.start.character)
    )

    assert items[0].message == "unnecessary command substitution within expression"
    assert items[0].code == "redundant-expr"
    assert items[0].range.start.line == 5
    assert items[0].range.start.character == 10
    assert items[0].range.end.line == 5
    assert items[0].range.end.character == 23

    assert (
        items[1].message == "expression with substitutions should be enclosed by braces"
    )
    assert items[1].code == "unbraced-expr"
    assert items[1].range.start.line == 5
    assert items[1].range.start.character == 16
    assert items[1].range.end.line == 5
    assert items[1].range.end.character == 22


@pytest.mark.asyncio
async def test_format(client: pytest_lsp.LanguageClient, tmp_path):
    """Formatting test."""
    params = lsp.InitializeParams(
        capabilities=get_capabilities("visual-studio-code"),
        workspace_folders=[
            lsp.WorkspaceFolder(uri=tmp_path.as_uri(), name=tmp_path.name)
        ],
    )
    await client.initialize_session(params)

    document = tmp_path / "source.tcl"

    INDENT_TEST = """if {{1}} {{
{}puts "hello"
}}
"""
    for source, expected, end in (
        ("foo", "foo\n", (0, 3)),
        ("foo\n\n\n\n\nbar\n", "foo\n\n\nbar\n", (6, 0)),
        (INDENT_TEST.format(""), INDENT_TEST.format("   "), (3, 0)),
    ):
        with open(document, "w") as f:
            f.write(source)

        result = await client.text_document_formatting_async(
            params=lsp.DocumentFormattingParams(
                text_document=lsp.TextDocumentIdentifier(uri=document.as_uri()),
                options=lsp.FormattingOptions(tab_size=3, insert_spaces=True),
            ),
        )
        assert len(result) == 1
        result = result[0]

        assert result.new_text == expected
        assert result.range.start.line == 0
        assert result.range.start.character == 0
        assert result.range.end.line == end[0]
        assert result.range.end.character == end[1]

    # Check that tclint config overrides client config
    config = tmp_path / "tclint.toml"
    with open(config, "w") as f:
        f.write("""[style]
indent = 'tab'""")

    client.workspace_did_change_watched_files(
        # `changes` isn't used by our server impl, so we can cheat and keep this empty
        params=lsp.DidChangeWatchedFilesParams(changes=[])
    )

    result = await client.text_document_formatting_async(
        params=lsp.DocumentFormattingParams(
            text_document=lsp.TextDocumentIdentifier(uri=document.as_uri()),
            options=lsp.FormattingOptions(tab_size=3, insert_spaces=True),
        ),
    )
    assert len(result) == 1
    result = result[0]

    assert result.new_text == INDENT_TEST.format("\t")
    assert result.range.start.line == 0
    assert result.range.start.character == 0
    assert result.range.end.line == 3
    assert result.range.end.character == 0


@pytest.mark.asyncio
async def test_format_range(client: pytest_lsp.LanguageClient, tmp_path):
    params = lsp.InitializeParams(
        capabilities=get_capabilities("visual-studio-code"),
        workspace_folders=[
            lsp.WorkspaceFolder(uri=tmp_path.as_uri(), name=tmp_path.name)
        ],
    )
    await client.initialize_session(params)

    document = tmp_path / "source.tcl"

    source = r"""
puts "hello"

    if {1} {
  puts  "world"
 }

puts "goodbye"
"""

    expected = r"""
    if {1} {
       puts "world"
    }
""".lstrip("\n")

    with open(document, "w") as f:
        f.write(source)

    result = await client.text_document_range_formatting_async(
        params=lsp.DocumentRangeFormattingParams(
            text_document=lsp.TextDocumentIdentifier(uri=document.as_uri()),
            options=lsp.FormattingOptions(tab_size=3, insert_spaces=True),
            range=lsp.Range(
                start=lsp.Position(line=3, character=8),
                end=lsp.Position(line=5, character=1),
            ),
        ),
    )
    assert len(result) == 1
    result = result[0]

    assert result.new_text == expected
    assert result.range.start.line == 3
    assert result.range.start.character == 0
    assert result.range.end.line == 6
    assert result.range.end.character == 0


@pytest.mark.asyncio
async def test_config(client: pytest_lsp.LanguageClient, tmp_path_factory):
    """Tests configuration reading, specifically:
    1) That configs for multiple workspaces are found and applied correctly.
    2) That diagnostics are refreshed correctly when config is updated.

    Note proper use of the client capabilities we rely on for file watching/diagnostic
    refresh aren't captured by this test, the client is controlled manually.
    """
    # Set up workspaces
    document = MY_DIR / "data" / "dirty.tcl"

    ws_foo = tmp_path_factory.mktemp("foo")
    with open(ws_foo / "tclint.toml", "w") as f:
        f.write("ignore = ['redundant-expr']")
    doc_foo = Path(shutil.copy(document, ws_foo))

    ws_bar = tmp_path_factory.mktemp("bar")
    with open(ws_bar / "tclint.toml", "w") as f:
        f.write("ignore = ['unbraced-expr']")
    doc_bar = Path(shutil.copy(document, ws_bar))

    # Initialize client
    params = lsp.InitializeParams(
        capabilities=get_capabilities("visual-studio-code"),
        workspace_folders=[
            lsp.WorkspaceFolder(uri=ws_foo.as_uri(), name=ws_foo.name),
            lsp.WorkspaceFolder(uri=ws_bar.as_uri(), name=ws_bar.name),
        ],
    )
    await client.initialize_session(params)

    # Check diagnostics for workspace "foo"
    results = await client.text_document_diagnostic_async(
        params=lsp.DocumentDiagnosticParams(
            text_document=lsp.TextDocumentIdentifier(uri=doc_foo.as_uri())
        )
    )
    assert results is not None
    assert len(results.items) == 1
    assert results.items[0].code == "unbraced-expr"

    # Check diagnostics for workspace "bar"
    results = await client.text_document_diagnostic_async(
        params=lsp.DocumentDiagnosticParams(
            text_document=lsp.TextDocumentIdentifier(uri=doc_bar.as_uri())
        )
    )
    assert results is not None
    assert len(results.items) == 1
    assert results.items[0].code == "redundant-expr"

    # Make sure diagnostics refresh when config file is updated
    with open(ws_foo / "tclint.toml", "w") as f:
        f.write("ignore = ['redundant-expr', 'unbraced-expr']")
    client.workspace_did_change_watched_files(
        # `changes` isn't used by our server impl, so we can cheat and keep this empty
        params=lsp.DidChangeWatchedFilesParams(changes=[])
    )

    results = await client.text_document_diagnostic_async(
        params=lsp.DocumentDiagnosticParams(
            text_document=lsp.TextDocumentIdentifier(uri=doc_foo.as_uri())
        )
    )
    assert results.items == []


@pytest.mark.asyncio
async def test_config_extension_settings(
    client: pytest_lsp.LanguageClient, tmp_path_factory
):
    """Tests configuration reading, similar to test_config, except with paths to the
    config files supplied to the LSP via initialization params settings.
    """
    # Set up workspaces
    document = MY_DIR / "data" / "dirty.tcl"

    ws_foo = tmp_path_factory.mktemp("foo")
    config_foo = ws_foo / "nondefault.toml"
    with open(config_foo, "w") as f:
        f.write("ignore = ['redundant-expr']")
    doc_foo = Path(shutil.copy(document, ws_foo))

    ws_bar = tmp_path_factory.mktemp("bar")
    config_bar = ws_bar / "nondefault.toml"
    with open(config_bar, "w") as f:
        f.write("ignore = ['unbraced-expr']")
    doc_bar = Path(shutil.copy(document, ws_bar))

    config_global = tmp_path_factory.mktemp("global") / "nondefault.toml"
    with open(config_global, "w") as f:
        f.write("ignore = ['redundant-expr', 'unbraced-expr']")

    # Initialize client
    params = lsp.InitializeParams(
        capabilities=get_capabilities("visual-studio-code"),
        workspace_folders=[
            lsp.WorkspaceFolder(uri=ws_foo.as_uri(), name=ws_foo.name),
            lsp.WorkspaceFolder(uri=ws_bar.as_uri(), name=ws_bar.name),
        ],
        initialization_options={
            "settings": [
                {
                    "cwd": ws_foo,
                    "configPath": config_foo,
                },
                {
                    "cwd": ws_bar,
                    "configPath": config_bar,
                },
            ],
            "globalSettings": {"cwd": "/", "configPath": config_global},
        },
    )
    await client.initialize_session(params)

    # Check diagnostics for workspace "foo"
    results = await client.text_document_diagnostic_async(
        params=lsp.DocumentDiagnosticParams(
            text_document=lsp.TextDocumentIdentifier(uri=doc_foo.as_uri())
        )
    )
    assert results is not None
    assert len(results.items) == 1
    assert results.items[0].code == "unbraced-expr"

    # Check diagnostics for workspace "bar"
    results = await client.text_document_diagnostic_async(
        params=lsp.DocumentDiagnosticParams(
            text_document=lsp.TextDocumentIdentifier(uri=doc_bar.as_uri())
        )
    )
    assert results is not None
    assert len(results.items) == 1
    assert results.items[0].code == "redundant-expr"

    # Check diagnostics for an unpatriated file, global config should apply here
    results = await client.text_document_diagnostic_async(
        params=lsp.DocumentDiagnosticParams(
            text_document=lsp.TextDocumentIdentifier(uri=document.as_uri())
        )
    )
    assert results is not None
    assert len(results.items) == 0


@pytest.mark.asyncio
async def test_invalid_config(client: pytest_lsp.LanguageClient, tmp_path_factory):
    # Set up workspace
    ws = tmp_path_factory.mktemp("ws")
    config = ws / "tclint.toml"
    # Invalid config
    with open(config, "w") as f:
        f.write("asdf")

    # Initialize client
    params = lsp.InitializeParams(
        capabilities=get_capabilities("visual-studio-code"),
        workspace_folders=[
            lsp.WorkspaceFolder(uri=ws.as_uri(), name=ws.name),
        ],
        initialization_options={
            "settings": [],
            "globalSettings": {"cwd": "/", "configPath": config},
        },
    )
    await client.initialize_session(params)
    await client.wait_for_notification(lsp.WINDOW_SHOW_MESSAGE)
    assert len(client.messages) == 1
    assert (
        client.messages[0].message
        == f"Error loading config file: {config}: Expected '=' after a key in a"
        " key/value pair (at end of document)"
    )


@pytest.mark.asyncio
async def test_nested_configs(client: pytest_lsp.LanguageClient, tmp_path_factory):
    # Set up workspaces
    parent_ws = tmp_path_factory.mktemp("ws")
    with open(parent_ws / "tclint.toml", "w") as f:
        f.write("ignore = []")
    child_ws = parent_ws / "child"
    child_ws.mkdir()
    with open(child_ws / "tclint.toml", "w") as f:
        f.write("ignore = ['command-args']")

    document = child_ws / "source.tcl"
    with open(document, "w") as f:
        # Missing arguments
        f.write("puts")

    # Initialize client
    params = lsp.InitializeParams(
        capabilities=get_capabilities("visual-studio-code"),
        workspace_folders=[
            lsp.WorkspaceFolder(uri=parent_ws.as_uri(), name=parent_ws.name),
            lsp.WorkspaceFolder(uri=child_ws.as_uri(), name=child_ws.name),
        ],
    )
    await client.initialize_session(params)
    results = await client.text_document_diagnostic_async(
        params=lsp.DocumentDiagnosticParams(
            text_document=lsp.TextDocumentIdentifier(uri=document.as_uri())
        )
    )
    assert results is not None
    assert len(results.items) == 0


@pytest.mark.asyncio
async def test_lsp_exclude(client: pytest_lsp.LanguageClient, tmp_path):
    """Test that files excluded by the config are ignored."""
    document = tmp_path / "excluded.tcl"
    config = tmp_path / "tclint.toml"

    with open(document, "w") as f:
        # Missing arguments
        f.write("puts")

    with open(config, "w") as f:
        f.write(f"exclude = ['{document.name}']")

    params = lsp.InitializeParams(
        capabilities=get_capabilities("visual-studio-code"),
        initialization_options={
            "globalSettings": {
                "configPath": config,
            },
        },
    )
    await client.initialize_session(params)

    results = await client.text_document_diagnostic_async(
        params=lsp.DocumentDiagnosticParams(
            text_document=lsp.TextDocumentIdentifier(uri=document.as_uri())
        )
    )
    assert results is not None
    assert len(results.items) == 0
