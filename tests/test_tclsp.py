from pathlib import Path
import shutil
import sys

from lsprotocol import types as lsp
import pytest
import pytest_lsp

MY_DIR = Path(__file__).parent.resolve()
LSP_BIN = MY_DIR / ".." / "src" / "tclint" / "cli" / "tclsp.py"


@pytest_lsp.fixture(
    config=pytest_lsp.ClientServerConfig(
        server_command=[sys.executable, str(LSP_BIN), "--disable-client-features"]
    )
)
async def client(lsp_client: pytest_lsp.LanguageClient, request):
    yield

    # Teardown
    await lsp_client.shutdown_session()


@pytest.mark.asyncio
async def test_diagnostics(client: pytest_lsp.LanguageClient):
    """Basic diagnostics test."""
    params = lsp.InitializeParams(
        capabilities=pytest_lsp.client_capabilities("visual-studio-code"),
    )
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
        capabilities=pytest_lsp.client_capabilities("visual-studio-code"),
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
