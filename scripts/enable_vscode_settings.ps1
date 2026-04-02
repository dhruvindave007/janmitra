# =============================================================================
# Enable VS Code Settings for JanMitra Project
# =============================================================================
# Automatically enables recommended settings for development
# =============================================================================

$ErrorActionPreference = "Continue"
$ProjectRoot = "C:\janmitra"
$VSCodeDir = "$ProjectRoot\.vscode"
$SettingsFile = "$VSCodeDir\settings.json"

function Write-Success { Write-Host "✓ $args" -ForegroundColor Green }
function Write-Info { Write-Host "ℹ $args" -ForegroundColor Cyan }

Write-Info "Configuring VS Code settings for JanMitra..."

# Create .vscode directory if it doesn't exist
if (-not (Test-Path $VSCodeDir)) {
    New-Item -ItemType Directory -Force -Path $VSCodeDir | Out-Null
    Write-Success "Created .vscode directory"
}

# Recommended settings for the project
$settings = @{
    # Python settings
    "python.terminal.useEnvFile" = $true
    "python.analysis.autoImportCompletions" = $true
    "python.analysis.typeCheckingMode" = "basic"
    "python.linting.enabled" = $true
    "python.linting.pylintEnabled" = $true
    "python.formatting.provider" = "autopep8"
    "python.testing.pytestEnabled" = $true
    "python.testing.unittestEnabled" = $true
    
    # Flutter/Dart settings
    "dart.flutterSdkPath" = $null
    "dart.debugExternalPackageLibraries" = $true
    "dart.debugSdkLibraries" = $false
    "[dart]" = @{
        "editor.formatOnSave" = $true
        "editor.formatOnType" = $true
        "editor.selectionHighlight" = $false
        "editor.suggest.snippetsPreventQuickSuggestions" = $false
        "editor.suggestSelection" = "first"
        "editor.tabCompletion" = "onlySnippets"
        "editor.wordBasedSuggestions" = $false
    }
    
    # General editor settings
    "files.autoSave" = "afterDelay"
    "files.autoSaveDelay" = 1000
    "editor.formatOnSave" = $true
    "editor.codeActionsOnSave" = @{
        "source.organizeImports" = $true
    }
    
    # Git settings
    "git.enableSmartCommit" = $true
    "git.autofetch" = $true
    
    # Docker settings
    "docker.showStartPage" = $false
    
    # Terminal settings
    "terminal.integrated.env.windows" = @{
        "PYTHONPATH" = "`${workspaceFolder}\backend"
    }
    
    # File associations
    "files.associations" = @{
        "*.env" = "dotenv"
        "docker-compose*.yml" = "yaml"
        "Dockerfile*" = "dockerfile"
    }
    
    # Exclude patterns
    "files.exclude" = @{
        "**/__pycache__" = $true
        "**/*.pyc" = $true
        "**/.pytest_cache" = $true
        "**/.mypy_cache" = $true
        "**/node_modules" = $true
        "**/.dart_tool" = $true
        "**/build" = $true
    }
    
    # Search exclude patterns
    "search.exclude" = @{
        "**/node_modules" = $true
        "**/bower_components" = $true
        "**/.git" = $true
        "**/.venv" = $true
        "**/.venv-1" = $true
        "**/staticfiles" = $true
        "**/media" = $true
        "**/.dart_tool" = $true
        "**/build" = $true
    }
}

# Convert to JSON
$settingsJson = $settings | ConvertTo-Json -Depth 10

# Save settings
$settingsJson | Out-File -FilePath $SettingsFile -Encoding UTF8 -Force

Write-Success "VS Code settings configured!"
Write-Info "Settings saved to: $SettingsFile"

# Create launch.json for debugging
$LaunchFile = "$VSCodeDir\launch.json"

$launchConfig = @{
    "version" = "0.2.0"
    "configurations" = @(
        @{
            "name" = "Python: Django"
            "type" = "python"
            "request" = "launch"
            "program" = "`${workspaceFolder}\backend\manage.py"
            "args" = @(
                "runserver"
                "0.0.0.0:8000"
            )
            "django" = $true
            "justMyCode" = $true
            "env" = @{
                "DJANGO_SETTINGS_MODULE" = "janmitra_backend.settings"
            }
        },
        @{
            "name" = "Flutter: Debug"
            "type" = "dart"
            "request" = "launch"
            "program" = "`${workspaceFolder}\mobile\lib\main.dart"
        },
        @{
            "name" = "Flutter: Profile"
            "type" = "dart"
            "request" = "launch"
            "program" = "`${workspaceFolder}\mobile\lib\main.dart"
            "flutterMode" = "profile"
        }
    )
}

$launchJson = $launchConfig | ConvertTo-Json -Depth 10
$launchJson | Out-File -FilePath $LaunchFile -Encoding UTF8 -Force

Write-Success "Debug configurations created!"
Write-Info "Launch configurations saved to: $LaunchFile"

# Create tasks.json for common tasks
$TasksFile = "$VSCodeDir\tasks.json"

$tasksConfig = @{
    "version" = "2.0.0"
    "tasks" = @(
        @{
            "label" = "Run Backend Tests"
            "type" = "shell"
            "command" = "docker-compose"
            "args" = @("exec", "-T", "django", "python", "manage.py", "test")
            "group" = "test"
            "presentation" = @{
                "reveal" = "always"
                "panel" = "new"
            }
        },
        @{
            "label" = "Run Flutter Tests"
            "type" = "shell"
            "command" = "flutter"
            "args" = @("test")
            "options" = @{
                "cwd" = "`${workspaceFolder}\mobile"
            }
            "group" = "test"
            "presentation" = @{
                "reveal" = "always"
                "panel" = "new"
            }
        },
        @{
            "label" = "Start Docker Services"
            "type" = "shell"
            "command" = "docker-compose"
            "args" = @("up", "-d")
            "group" = "build"
        },
        @{
            "label" = "Stop Docker Services"
            "type" = "shell"
            "command" = "docker-compose"
            "args" = @("down")
        },
        @{
            "label" = "Run Automated Tests"
            "type" = "shell"
            "command" = "powershell"
            "args" = @("-ExecutionPolicy", "Bypass", "-File", "`${workspaceFolder}\scripts\automated_debug_test.ps1")
            "group" = @{
                "kind" = "test"
                "isDefault" = $true
            }
        }
    )
}

$tasksJson = $tasksConfig | ConvertTo-Json -Depth 10
$tasksJson | Out-File -FilePath $TasksFile -Encoding UTF8 -Force

Write-Success "Task configurations created!"
Write-Info "Tasks saved to: $TasksFile"

Write-Info ""
Write-Success "All VS Code settings have been configured!"
Write-Info "You can now:"
Write-Info "  - Use environment variables from .env in terminals"
Write-Info "  - Debug Django with F5"
Write-Info "  - Debug Flutter with F5"
Write-Info "  - Run tests with Ctrl+Shift+P > Tasks: Run Task"
