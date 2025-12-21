# Editor Integration

The `tclint` project includes a language server, `tclsp`, which integrates diagnostics
and formatting into editors.

## Configuration

`tclsp` searches for `tclint` configuration files according to the rules in [config discovery](configuration.md#config-discovery).
The one difference is that the LSP will not search for files above the root of the workspace.
`tclsp` defaults to the client-provided setting for indentation, but this will be overridden by an explicit setting in a config file.

On initialization, a client may provide `tclsp` with explicit paths to configuration files via [`InitializeParams.initializationOptions`][initialize-params].
This detail only concerns advanced users who are manually configuring LSP integration with their editor.
For VS Code users, this is handled automatically by the [extension][vscode]. The options are expected to match a schema like the following:

```jsonc
{
  // global config, applies to all files (if no workspace config applies)
  "globalSettings": {
    "configPath": "/path/to/global/config.toml"
  },
  // workspace configs, each applies to files under corresponding `cwd`
  "settings": [{
    "cwd": "/path/to/workspace/folder",
    "configPath": "/path/to/workspace/config.toml",
  }]
}
```

Note that this schema is likely to change in a future release.

## Supported Editors

This language server should be compatible with any editor that supports the Language
Server Protocol. It has been tested with the following editors:
- Visual Studio Code
- Neovim
- Emacs

The following sections document the basics required to get `tclsp` working with these
editors. Advanced Neovim and Emacs users will likely want to tweak their configurations
to taste.

### Visual Studio Code

Download the Visual Studio Code extension from the [Extension Marketplace][vscode].

### Neovim

To enable `tclsp` in Neovim, add the following Lua configuration:

```lua
-- Optional, if these filetypes aren't defined and you want to support them.
vim.filetype.add {
  pattern = {
    ['.*.xdc'] = 'xdc',
    ['.*.upf'] = 'upf',
  },
}

vim.api.nvim_create_autocmd('FileType', {
  pattern = 'tcl,sdc,xdc,upf',
  callback = function(args)
    vim.lsp.start({
      name = 'tclint',
      cmd = {'tclsp'},
      root_dir = vim.fs.root(args.buf, {'tclint.toml', '.tclint', 'pyproject.toml'}),
    })
  end,
})
```

#### Compatibility

`tclsp` requires Neovim version 0.10 or newer.

Due to an unsupported LSP feature, Neovim will not automatically refresh diagnostics
when the `tclint` configuration file is updated.

### Emacs

Using `tclsp` in Emacs requires `lsp-mode`. Follow these
[instructions](https://emacs-lsp.github.io/lsp-mode/page/installation/) to install it.
Note that you must install a bleeding edge release; the current stable
release (9.0.0) lacks support for a required feature.

Add the following to your Emacs configuration to associate `tclsp` with the default
supported filetypes:

```emacs-lisp
(with-eval-after-load 'lsp-mode
    (add-to-list 'lsp-language-id-configuration '(tcl-mode . "tcl"))
    (add-to-list 'lsp-language-id-configuration '(".*\\.sdc" . "tcl"))
    (add-to-list 'lsp-language-id-configuration '(".*\\.xdc" . "tcl"))
    (add-to-list 'lsp-language-id-configuration '(".*\\.upf" . "tcl"))

    (lsp-register-client (make-lsp-client
                      :new-connection (lsp-stdio-connection "tclsp")
                      :activation-fn (lsp-activate-on "tcl")
                      :server-id 'tclint)))
```

To activate `lsp-mode` in your current buffer, call `M-x lsp`.

#### Compatibility

Due to an unsupported LSP feature, Emacs will not automatically refresh diagnostics when
the `tclint` configuration file is updated.

## Formatting

`tclsp` supports both document and range/selection formatting according to the `tclfmt`
[rules](tclfmt.md). When formatting a selection that only includes part of a line,
`tclsp` will effectively extend the selection to format the entire line.

When formatting a range, `tclsp` preserves leading indentation and leading and trailing whitespace.

[vscode]: https://marketplace.visualstudio.com/items?itemName=nmoroze.tclint
[initialize-params]: https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#initializeParams
