# Source - https://stackoverflow.com/a/43697842
# Posted by David Brabant, modified by community. See post 'Timeline' for change history
# Retrieved 2026-01-16, License - CC BY-SA 4.0


################################ Read INI File ##################################

. .\lib\powershell\read_ini.ps1

$iniFile = Get-IniFile .\ffxiv_config.ini

# $app = $iniFile.NoSection.APP
# $dll = $iniFile.NoSection.DLL

$ffxivInstallation = $iniFile.local.ffxiv_installation
Write-Host "FFXIV Installation Path: $ffxivInstallation"

$saintCoinachPath = $iniFile.local.icon_directory
Write-Host "SaintCoinach Path: $saintCoinachPath"

if (-not $saintCoinachPath) {
  Write-Error "SaintCoinach path not set in ffxiv_config.ini"
  exit 1
}

if (-not (Test-Path $ffxivInstallation)) {
  Write-Error "FFXIV installation path '$ffxivInstallation' does not exist!"
  exit 1
}


# Validate all required config keys exist
$requiredKeys = @('ffxiv_installation', 'icon_directory')
foreach ($key in $requiredKeys) {
  if (-not $iniFile.local.$key) {
    Write-Error "Missing required config key: local.$key"
    exit 1
  }
}


################################## Delete old files ##################################

# get most recent directory from SaintCoinach path that matches YYYY.MM.DD.HHMM.SSSS format and delete the others

Get-ChildItem -Path $saintCoinachPath | Where-Object { $_.PSIsContainer -and $_.Name -match '^\d{4}\.\d{2}\.\d{2}\.\d{4}\.\d{4}$' } | Sort-Object Name -Descending | Select-Object -Skip 1 | ForEach-Object {
  $dirToDelete = $_.FullName
  Write-Host "Deleting old SaintCoinach directory: $dirToDelete"
  Remove-Item -Path $dirToDelete -Recurse -Force
}


################################### Update SaintCoinach ###################################

# Change to the SaintCoinach directory
$originalLocation = Get-Location
try {
  Set-Location $saintCoinachPath
  Write-Output "Updating SaintCoinach.Cmd..."

  try {
    # Get the latest release information from GitHub API
    $latestRelease = Invoke-RestMethod -Uri "https://api.github.com/repos/xivapi/SaintCoinach/releases/latest"

    # Find the SaintCoinach.Cmd.zip asset
    $downloadUrl = ($latestRelease.assets | Where-Object { $_.name -match "SaintCoinach.Cmd.zip" }).browser_download_url

    if (-not $downloadUrl) {
      Write-Error "SaintCoinach.Cmd.zip not found in latest release"
      exit 1
    }

    Write-Output "Downloading from: $downloadUrl"

    # Download the file
    Invoke-WebRequest -Uri $downloadUrl -OutFile "SaintCoinach.Cmd.zip"

    if (-not (Test-Path "SaintCoinach.Cmd.zip")) {
      Write-Error "Download failed or file does not exist."
      exit 1
    }

    Write-Output "Extracting SaintCoinach.Cmd.zip..."

    # Extract the zip file
    Expand-Archive -Path "SaintCoinach.Cmd.zip" -DestinationPath "." -Force

    # Delete SaintCoinach.History.zip if it exists
    if (Test-Path "SaintCoinach.History.zip") {
      Remove-Item "SaintCoinach.History.zip"
      Write-Output "Deleted SaintCoinach.History.zip"
    }

    # Run SaintCoinach.Cmd
    Write-Output "Running SaintCoinach.Cmd..."
    & ".\SaintCoinach.Cmd.exe" $ffxivInstallation "ui" "uihd"

    # After successful extraction
    Remove-Item "SaintCoinach.Cmd.zip" -Force
    Write-Output "Cleaned up download file"

    Write-Output "Script completed successfully."

  }
  catch {
    Write-Error "An error occurred: $($_.Exception.Message)"
    exit 1
  }
}
finally {
  Set-Location $originalLocation
}


############################### Run Upload Script ##################################

# Complain if Poetry is not installed
if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
  Write-Error "Poetry is not installed. Please install Poetry to continue."
  exit 1
}

Set-Location $PSScriptRoot
poetry run update_achievement_images.py