"""
apps_list.py - Pre-loaded list of 100 common Windows applications.
"""

import os
import glob

APP_CATEGORIES = [
    "Browser",
    "Communication",
    "Gaming",
    "Media",
    "Productivity",
    "Development",
    "Creative",
    "Utility",
    "Remote",
    "Virtualization",
    "Game Engine",
    "System",
]


def _p(path: str) -> str:
    """Expand environment variables in a path string."""
    return os.path.expandvars(path)


DEFAULT_APPS = [
    # ── Browser ──────────────────────────────────────────────────────────────
    {
        "name": "Google Chrome",
        "category": "Browser",
        "exe_name": "chrome.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Google\Chrome\Application"),
            _p(r"%ProgramFiles(x86)%\Google\Chrome\Application"),
            _p(r"%LocalAppData%\Google\Chrome\Application"),
        ],
    },
    {
        "name": "Mozilla Firefox",
        "category": "Browser",
        "exe_name": "firefox.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Mozilla Firefox"),
            _p(r"%ProgramFiles(x86)%\Mozilla Firefox"),
        ],
    },
    {
        "name": "Microsoft Edge",
        "category": "Browser",
        "exe_name": "msedge.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles(x86)%\Microsoft\Edge\Application"),
            _p(r"%ProgramFiles%\Microsoft\Edge\Application"),
        ],
    },
    {
        "name": "Opera",
        "category": "Browser",
        "exe_name": "opera.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Programs\Opera"),
            _p(r"%AppData%\Opera Software\Opera Stable"),
        ],
    },
    {
        "name": "Brave Browser",
        "category": "Browser",
        "exe_name": "brave.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application"),
            _p(r"%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application"),
            _p(r"%LocalAppData%\BraveSoftware\Brave-Browser\Application"),
        ],
    },
    {
        "name": "Vivaldi",
        "category": "Browser",
        "exe_name": "vivaldi.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Vivaldi\Application"),
            _p(r"%ProgramFiles%\Vivaldi\Application"),
        ],
    },
    # ── Communication ────────────────────────────────────────────────────────
    {
        "name": "Discord",
        "category": "Communication",
        "exe_name": "discord.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Discord"),
            _p(r"%AppData%\Discord"),
        ],
    },
    {
        "name": "Slack",
        "category": "Communication",
        "exe_name": "slack.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\slack"),
            _p(r"%ProgramFiles%\Slack"),
            _p(r"%ProgramFiles(x86)%\Slack"),
        ],
    },
    {
        "name": "Microsoft Teams",
        "category": "Communication",
        "exe_name": "ms-teams.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Microsoft\Teams"),
            _p(r"%ProgramFiles(x86)%\Microsoft\Teams"),
            _p(r"%ProgramFiles%\Microsoft\Teams"),
            _p(r"%LocalAppData%\Microsoft\WindowsApps"),
        ],
    },
    {
        "name": "Zoom",
        "category": "Communication",
        "exe_name": "zoom.exe",
        "root_folder_hints": [
            _p(r"%AppData%\Zoom\bin"),
            _p(r"%ProgramFiles%\Zoom\bin"),
            _p(r"%ProgramFiles(x86)%\Zoom\bin"),
        ],
    },
    {
        "name": "Skype",
        "category": "Communication",
        "exe_name": "skype.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles(x86)%\Microsoft\Skype for Desktop"),
            _p(r"%ProgramFiles%\Microsoft\Skype for Desktop"),
            _p(r"%AppData%\Microsoft\Skype"),
        ],
    },
    {
        "name": "Telegram Desktop",
        "category": "Communication",
        "exe_name": "telegram.exe",
        "root_folder_hints": [
            _p(r"%AppData%\Telegram Desktop"),
            _p(r"%LocalAppData%\Telegram Desktop"),
            _p(r"%ProgramFiles%\Telegram Desktop"),
        ],
    },
    {
        "name": "WhatsApp",
        "category": "Communication",
        "exe_name": "whatsapp.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\WhatsApp"),
            _p(r"%AppData%\WhatsApp"),
        ],
    },
    {
        "name": "Signal",
        "category": "Communication",
        "exe_name": "signal.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Programs\signal-desktop"),
            _p(r"%AppData%\Signal"),
        ],
    },
    {
        "name": "Viber",
        "category": "Communication",
        "exe_name": "viber.exe",
        "root_folder_hints": [
            _p(r"%AppData%\Viber"),
            _p(r"%LocalAppData%\Viber"),
            _p(r"%ProgramFiles%\Viber"),
        ],
    },
    {
        "name": "TeamSpeak 3",
        "category": "Communication",
        "exe_name": "ts3client_win64.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\TeamSpeak 3 Client"),
            _p(r"%ProgramFiles(x86)%\TeamSpeak 3 Client"),
            _p(r"%AppData%\TeamSpeak 3 Client"),
        ],
    },
    # ── Gaming ───────────────────────────────────────────────────────────────
    {
        "name": "Steam",
        "category": "Gaming",
        "exe_name": "steam.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles(x86)%\Steam"),
            _p(r"%ProgramFiles%\Steam"),
        ],
    },
    {
        "name": "Epic Games Launcher",
        "category": "Gaming",
        "exe_name": "epicgameslauncher.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles(x86)%\Epic Games\Launcher\Portal\Binaries\Win32"),
            _p(r"%ProgramFiles%\Epic Games\Launcher\Portal\Binaries\Win64"),
            _p(r"%LocalAppData%\EpicGamesLauncher\Saved\Config"),
        ],
    },
    {
        "name": "GOG Galaxy",
        "category": "Gaming",
        "exe_name": "galaxyclient.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles(x86)%\GOG Galaxy"),
            _p(r"%ProgramFiles%\GOG Galaxy"),
        ],
    },
    {
        "name": "EA App",
        "category": "Gaming",
        "exe_name": "eadesktop.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Electronic Arts\EA Desktop"),
            _p(r"%ProgramFiles(x86)%\Electronic Arts\EA Desktop"),
        ],
    },
    {
        "name": "Battle.net",
        "category": "Gaming",
        "exe_name": "battle.net.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles(x86)%\Battle.net"),
            _p(r"%ProgramFiles%\Battle.net"),
        ],
    },
    {
        "name": "Ubisoft Connect",
        "category": "Gaming",
        "exe_name": "ubisoftconnect.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles(x86)%\Ubisoft\Ubisoft Game Launcher"),
            _p(r"%ProgramFiles%\Ubisoft\Ubisoft Game Launcher"),
        ],
    },
    {
        "name": "Xbox App",
        "category": "Gaming",
        "exe_name": "xboxapp.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\WindowsApps\Microsoft.GamingApp*"),
            _p(r"%LocalAppData%\Microsoft\WindowsApps"),
        ],
    },
    {
        "name": "Minecraft Launcher",
        "category": "Gaming",
        "exe_name": "minecraftlauncher.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Minecraft Launcher"),
            _p(r"%ProgramFiles(x86)%\Minecraft Launcher"),
            _p(r"%LocalAppData%\Packages\Microsoft.4297127D64EC6_*\LocalCache"),
        ],
    },
    {
        "name": "Roblox Player",
        "category": "Gaming",
        "exe_name": "robloxplayerbeta.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Roblox\Versions"),
            _p(r"%LocalAppData%\Roblox"),
        ],
    },
    {
        "name": "Riot Client",
        "category": "Gaming",
        "exe_name": "riotclientservices.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Riot Vanguard"),
            _p(r"%LocalAppData%\Riot Games\RiotClientInstalls"),
            _p(r"%ProgramFiles(x86)%\Riot Games\Riot Client"),
        ],
    },
    {
        "name": "League of Legends",
        "category": "Gaming",
        "exe_name": "leagueoflegends.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Riot Games\League of Legends\Game"),
            _p(r"C:\Riot Games\League of Legends\Game"),
        ],
    },
    {
        "name": "Valorant",
        "category": "Gaming",
        "exe_name": "valorant.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Riot Games\VALORANT\live\ShooterGame\Binaries\Win64"),
            _p(r"C:\Riot Games\VALORANT\live\ShooterGame\Binaries\Win64"),
        ],
    },
    {
        "name": "Twitch",
        "category": "Gaming",
        "exe_name": "twitch.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Twitch"),
            _p(r"%ProgramFiles(x86)%\Twitch"),
            _p(r"%AppData%\Twitch"),
        ],
    },
    # ── Media ────────────────────────────────────────────────────────────────
    {
        "name": "Spotify",
        "category": "Media",
        "exe_name": "spotify.exe",
        "root_folder_hints": [
            _p(r"%AppData%\Spotify"),
            _p(r"%LocalAppData%\Microsoft\WindowsApps"),
            _p(r"%ProgramFiles%\Spotify"),
        ],
    },
    {
        "name": "VLC Media Player",
        "category": "Media",
        "exe_name": "vlc.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\VideoLAN\VLC"),
            _p(r"%ProgramFiles(x86)%\VideoLAN\VLC"),
        ],
    },
    {
        "name": "iTunes",
        "category": "Media",
        "exe_name": "itunes.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\iTunes"),
            _p(r"%ProgramFiles(x86)%\iTunes"),
        ],
    },
    {
        "name": "foobar2000",
        "category": "Media",
        "exe_name": "foobar2000.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\foobar2000"),
            _p(r"%ProgramFiles(x86)%\foobar2000"),
            _p(r"%AppData%\foobar2000"),
        ],
    },
    {
        "name": "MusicBee",
        "category": "Media",
        "exe_name": "musicbee.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\MusicBee"),
            _p(r"%ProgramFiles(x86)%\MusicBee"),
            _p(r"%AppData%\MusicBee"),
        ],
    },
    {
        "name": "Plex",
        "category": "Media",
        "exe_name": "plex.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Plex"),
            _p(r"%ProgramFiles%\Plex\Plex"),
            _p(r"%ProgramFiles(x86)%\Plex\Plex"),
        ],
    },
    {
        "name": "Kodi",
        "category": "Media",
        "exe_name": "kodi.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Kodi"),
            _p(r"%ProgramFiles(x86)%\Kodi"),
        ],
    },
    {
        "name": "HandBrake",
        "category": "Media",
        "exe_name": "handbrake.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\HandBrake"),
            _p(r"%ProgramFiles(x86)%\HandBrake"),
        ],
    },
    {
        "name": "Netflix",
        "category": "Media",
        "exe_name": "netflix.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Microsoft\WindowsApps"),
            _p(r"%ProgramFiles%\WindowsApps\4DF9E0F8.Netflix*"),
        ],
    },
    # ── Productivity ─────────────────────────────────────────────────────────
    {
        "name": "Microsoft Word",
        "category": "Productivity",
        "exe_name": "WINWORD.EXE",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Microsoft Office\root\Office16"),
            _p(r"%ProgramFiles(x86)%\Microsoft Office\root\Office16"),
            _p(r"%ProgramFiles%\Microsoft Office\Office16"),
            _p(r"%ProgramFiles(x86)%\Microsoft Office\Office16"),
        ],
    },
    {
        "name": "Microsoft Excel",
        "category": "Productivity",
        "exe_name": "EXCEL.EXE",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Microsoft Office\root\Office16"),
            _p(r"%ProgramFiles(x86)%\Microsoft Office\root\Office16"),
            _p(r"%ProgramFiles%\Microsoft Office\Office16"),
            _p(r"%ProgramFiles(x86)%\Microsoft Office\Office16"),
        ],
    },
    {
        "name": "Microsoft PowerPoint",
        "category": "Productivity",
        "exe_name": "POWERPNT.EXE",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Microsoft Office\root\Office16"),
            _p(r"%ProgramFiles(x86)%\Microsoft Office\root\Office16"),
            _p(r"%ProgramFiles%\Microsoft Office\Office16"),
            _p(r"%ProgramFiles(x86)%\Microsoft Office\Office16"),
        ],
    },
    {
        "name": "Microsoft Outlook",
        "category": "Productivity",
        "exe_name": "OUTLOOK.EXE",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Microsoft Office\root\Office16"),
            _p(r"%ProgramFiles(x86)%\Microsoft Office\root\Office16"),
            _p(r"%ProgramFiles%\Microsoft Office\Office16"),
            _p(r"%ProgramFiles(x86)%\Microsoft Office\Office16"),
        ],
    },
    {
        "name": "Microsoft OneNote",
        "category": "Productivity",
        "exe_name": "ONENOTE.EXE",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Microsoft Office\root\Office16"),
            _p(r"%ProgramFiles(x86)%\Microsoft Office\root\Office16"),
            _p(r"%LocalAppData%\Microsoft\WindowsApps"),
        ],
    },
    {
        "name": "Notion",
        "category": "Productivity",
        "exe_name": "notion.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Programs\Notion"),
            _p(r"%AppData%\Notion"),
        ],
    },
    {
        "name": "Obsidian",
        "category": "Productivity",
        "exe_name": "obsidian.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Programs\obsidian"),
            _p(r"%AppData%\obsidian"),
        ],
    },
    {
        "name": "Todoist",
        "category": "Productivity",
        "exe_name": "todoist.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Programs\todoist"),
            _p(r"%AppData%\Todoist"),
        ],
    },
    {
        "name": "Evernote",
        "category": "Productivity",
        "exe_name": "evernote.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Evernote\Evernote"),
            _p(r"%ProgramFiles(x86)%\Evernote\Evernote"),
            _p(r"%LocalAppData%\Programs\Evernote"),
        ],
    },
    {
        "name": "Trello",
        "category": "Productivity",
        "exe_name": "trello.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Programs\trello"),
            _p(r"%AppData%\Trello"),
        ],
    },
    {
        "name": "LibreOffice Writer",
        "category": "Productivity",
        "exe_name": "swriter.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\LibreOffice\program"),
            _p(r"%ProgramFiles(x86)%\LibreOffice\program"),
        ],
    },
    {
        "name": "Notepad",
        "category": "Productivity",
        "exe_name": "notepad.exe",
        "root_folder_hints": [
            _p(r"%SystemRoot%\System32"),
            _p(r"%SystemRoot%"),
        ],
    },
    # ── Development ──────────────────────────────────────────────────────────
    {
        "name": "Visual Studio Code",
        "category": "Development",
        "exe_name": "Code.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Programs\Microsoft VS Code"),
            _p(r"%ProgramFiles%\Microsoft VS Code"),
            _p(r"%ProgramFiles(x86)%\Microsoft VS Code"),
        ],
    },
    {
        "name": "Visual Studio 2022",
        "category": "Development",
        "exe_name": "devenv.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Microsoft Visual Studio\2022\Community\Common7\IDE"),
            _p(r"%ProgramFiles%\Microsoft Visual Studio\2022\Professional\Common7\IDE"),
            _p(r"%ProgramFiles%\Microsoft Visual Studio\2022\Enterprise\Common7\IDE"),
        ],
    },
    {
        "name": "PyCharm",
        "category": "Development",
        "exe_name": "pycharm64.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Programs\PyCharm Community"),
            _p(r"%LocalAppData%\Programs\PyCharm Professional"),
            _p(r"%ProgramFiles%\JetBrains\PyCharm Community*\bin"),
            _p(r"%ProgramFiles%\JetBrains\PyCharm Professional*\bin"),
        ],
    },
    {
        "name": "IntelliJ IDEA",
        "category": "Development",
        "exe_name": "idea64.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\JetBrains\IntelliJ IDEA*\bin"),
            _p(r"%LocalAppData%\Programs\IntelliJ IDEA"),
        ],
    },
    {
        "name": "WebStorm",
        "category": "Development",
        "exe_name": "webstorm64.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\JetBrains\WebStorm*\bin"),
            _p(r"%LocalAppData%\Programs\WebStorm"),
        ],
    },
    {
        "name": "Android Studio",
        "category": "Development",
        "exe_name": "studio64.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Android\Android Studio\bin"),
            _p(r"%LocalAppData%\Programs\Android Studio\bin"),
        ],
    },
    {
        "name": "GitHub Desktop",
        "category": "Development",
        "exe_name": "githubdesktop.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\GitHubDesktop"),
            _p(r"%AppData%\GitHub Desktop"),
        ],
    },
    {
        "name": "Git Bash",
        "category": "Development",
        "exe_name": "git-bash.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Git"),
            _p(r"%ProgramFiles(x86)%\Git"),
        ],
    },
    {
        "name": "Postman",
        "category": "Development",
        "exe_name": "postman.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Postman"),
            _p(r"%AppData%\Postman"),
        ],
    },
    {
        "name": "Windows Terminal",
        "category": "Development",
        "exe_name": "wt.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Microsoft\WindowsApps"),
            _p(r"%ProgramFiles%\WindowsApps\Microsoft.WindowsTerminal*"),
        ],
    },
    # ── Creative ─────────────────────────────────────────────────────────────
    {
        "name": "Adobe Photoshop",
        "category": "Creative",
        "exe_name": "photoshop.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Adobe\Adobe Photoshop*"),
            _p(r"%ProgramFiles(x86)%\Adobe\Adobe Photoshop*"),
        ],
    },
    {
        "name": "Adobe Illustrator",
        "category": "Creative",
        "exe_name": "illustrator.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Adobe\Adobe Illustrator*"),
            _p(r"%ProgramFiles(x86)%\Adobe\Adobe Illustrator*"),
        ],
    },
    {
        "name": "Adobe Premiere Pro",
        "category": "Creative",
        "exe_name": "adobe premiere pro.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Adobe\Adobe Premiere Pro*"),
            _p(r"%ProgramFiles(x86)%\Adobe\Adobe Premiere Pro*"),
        ],
    },
    {
        "name": "Adobe After Effects",
        "category": "Creative",
        "exe_name": "afterfx.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Adobe\Adobe After Effects*"),
            _p(r"%ProgramFiles(x86)%\Adobe\Adobe After Effects*"),
        ],
    },
    {
        "name": "GIMP",
        "category": "Creative",
        "exe_name": "gimp-2.10.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\GIMP 2\bin"),
            _p(r"%ProgramFiles(x86)%\GIMP 2\bin"),
        ],
    },
    {
        "name": "OBS Studio",
        "category": "Creative",
        "exe_name": "obs64.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\obs-studio\bin\64bit"),
            _p(r"%ProgramFiles(x86)%\obs-studio\bin\64bit"),
        ],
    },
    {
        "name": "DaVinci Resolve",
        "category": "Creative",
        "exe_name": "Resolve.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Blackmagic Design\DaVinci Resolve"),
        ],
    },
    {
        "name": "Blender",
        "category": "Creative",
        "exe_name": "blender.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Blender Foundation\Blender*"),
            _p(r"%ProgramFiles(x86)%\Blender Foundation\Blender*"),
        ],
    },
    {
        "name": "Paint.NET",
        "category": "Creative",
        "exe_name": "PaintDotNet.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\paint.net"),
            _p(r"%ProgramFiles(x86)%\paint.net"),
            _p(r"%LocalAppData%\Programs\paint.net"),
        ],
    },
    {
        "name": "Audacity",
        "category": "Creative",
        "exe_name": "audacity.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Audacity"),
            _p(r"%ProgramFiles(x86)%\Audacity"),
        ],
    },
    {
        "name": "Figma",
        "category": "Creative",
        "exe_name": "Figma.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Figma"),
            _p(r"%AppData%\Figma"),
        ],
    },
    {
        "name": "Inkscape",
        "category": "Creative",
        "exe_name": "inkscape.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Inkscape"),
            _p(r"%ProgramFiles(x86)%\Inkscape"),
        ],
    },
    # ── Utility ──────────────────────────────────────────────────────────────
    {
        "name": "Notepad++",
        "category": "Utility",
        "exe_name": "notepad++.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Notepad++"),
            _p(r"%ProgramFiles(x86)%\Notepad++"),
            _p(r"%LocalAppData%\Programs\Notepad++"),
        ],
    },
    {
        "name": "7-Zip",
        "category": "Utility",
        "exe_name": "7zFM.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\7-Zip"),
            _p(r"%ProgramFiles(x86)%\7-Zip"),
        ],
    },
    {
        "name": "WinRAR",
        "category": "Utility",
        "exe_name": "winrar.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\WinRAR"),
            _p(r"%ProgramFiles(x86)%\WinRAR"),
        ],
    },
    {
        "name": "Everything",
        "category": "Utility",
        "exe_name": "everything.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Everything"),
            _p(r"%ProgramFiles(x86)%\Everything"),
            _p(r"%LocalAppData%\Programs\Everything"),
        ],
    },
    {
        "name": "f.lux",
        "category": "Utility",
        "exe_name": "flux.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\FluxSoftware\Flux"),
            _p(r"%ProgramFiles%\f.lux"),
        ],
    },
    {
        "name": "ShareX",
        "category": "Utility",
        "exe_name": "sharex.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\ShareX"),
            _p(r"%ProgramFiles(x86)%\ShareX"),
            _p(r"%LocalAppData%\Programs\ShareX"),
        ],
    },
    {
        "name": "AutoHotkey",
        "category": "Utility",
        "exe_name": "autohotkey.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\AutoHotkey"),
            _p(r"%ProgramFiles(x86)%\AutoHotkey"),
        ],
    },
    {
        "name": "CPU-Z",
        "category": "Utility",
        "exe_name": "cpuz_x64.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\CPUID\CPU-Z"),
            _p(r"%ProgramFiles(x86)%\CPUID\CPU-Z"),
        ],
    },
    {
        "name": "HWiNFO",
        "category": "Utility",
        "exe_name": "HWiNFO64.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\HWiNFO64"),
            _p(r"%ProgramFiles(x86)%\HWiNFO64"),
            _p(r"%ProgramFiles%\HWiNFO"),
        ],
    },
    {
        "name": "MSI Afterburner",
        "category": "Utility",
        "exe_name": "msiafterburner.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles(x86)%\MSI Afterburner"),
            _p(r"%ProgramFiles%\MSI Afterburner"),
        ],
    },
    {
        "name": "TreeSize Free",
        "category": "Utility",
        "exe_name": "TreeSize.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\JAM Software\TreeSize Free"),
            _p(r"%ProgramFiles(x86)%\JAM Software\TreeSize Free"),
        ],
    },
    {
        "name": "WizTree",
        "category": "Utility",
        "exe_name": "WizTree64.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\WizTree"),
            _p(r"%ProgramFiles(x86)%\WizTree"),
        ],
    },
    # ── Remote ───────────────────────────────────────────────────────────────
    {
        "name": "AnyDesk",
        "category": "Remote",
        "exe_name": "anydesk.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\AnyDesk"),
            _p(r"%ProgramFiles(x86)%\AnyDesk"),
            _p(r"%AppData%\AnyDesk"),
            _p(r"%LocalAppData%\AnyDesk"),
        ],
    },
    {
        "name": "TeamViewer",
        "category": "Remote",
        "exe_name": "teamviewer.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\TeamViewer"),
            _p(r"%ProgramFiles(x86)%\TeamViewer"),
        ],
    },
    {
        "name": "PuTTY",
        "category": "Remote",
        "exe_name": "putty.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\PuTTY"),
            _p(r"%ProgramFiles(x86)%\PuTTY"),
            _p(r"%LocalAppData%\Programs\PuTTY"),
        ],
    },
    {
        "name": "WinSCP",
        "category": "Remote",
        "exe_name": "winscp.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\WinSCP"),
            _p(r"%ProgramFiles(x86)%\WinSCP"),
        ],
    },
    {
        "name": "FileZilla",
        "category": "Remote",
        "exe_name": "filezilla.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\FileZilla FTP Client"),
            _p(r"%ProgramFiles(x86)%\FileZilla FTP Client"),
            _p(r"%LocalAppData%\Programs\FileZilla FTP Client"),
        ],
    },
    {
        "name": "Wireshark",
        "category": "Remote",
        "exe_name": "wireshark.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Wireshark"),
            _p(r"%ProgramFiles(x86)%\Wireshark"),
        ],
    },
    # ── Virtualization ───────────────────────────────────────────────────────
    {
        "name": "VirtualBox",
        "category": "Virtualization",
        "exe_name": "virtualbox.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Oracle\VirtualBox"),
            _p(r"%ProgramFiles(x86)%\Oracle\VirtualBox"),
        ],
    },
    {
        "name": "VMware Workstation",
        "category": "Virtualization",
        "exe_name": "vmware.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles(x86)%\VMware\VMware Workstation"),
            _p(r"%ProgramFiles%\VMware\VMware Workstation"),
        ],
    },
    {
        "name": "Docker Desktop",
        "category": "Virtualization",
        "exe_name": "Docker Desktop.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Docker\Docker"),
            _p(r"%ProgramFiles(x86)%\Docker\Docker"),
            _p(r"%LocalAppData%\Docker"),
        ],
    },
    # ── Game Engine ──────────────────────────────────────────────────────────
    {
        "name": "Unity Hub",
        "category": "Game Engine",
        "exe_name": "Unity Hub.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Unity Hub"),
            _p(r"%ProgramFiles(x86)%\Unity Hub"),
            _p(r"%LocalAppData%\Programs\Unity Hub"),
        ],
    },
    {
        "name": "Unreal Engine",
        "category": "Game Engine",
        "exe_name": "UnrealEditor.exe",
        "root_folder_hints": [
            _p(r"%ProgramFiles%\Epic Games\UE_*\Engine\Binaries\Win64"),
            _p(r"C:\Program Files\Epic Games\UE_*\Engine\Binaries\Win64"),
        ],
    },
    # ── System ───────────────────────────────────────────────────────────────
    # Task Manager and PowerShell are deliberately NOT offered here. They are
    # in core/protected.py: FocusGuard must never be able to close the tools a
    # user needs to inspect or stop FocusGuard, and an app that terminates
    # Task Manager on a loop is what antivirus heuristics score as a trojan.
    {
        "name": "Calculator",
        "category": "System",
        "exe_name": "calc.exe",
        "root_folder_hints": [
            _p(r"%SystemRoot%\System32"),
            _p(r"%LocalAppData%\Microsoft\WindowsApps"),
        ],
    },
    {
        "name": "Paint",
        "category": "System",
        "exe_name": "mspaint.exe",
        "root_folder_hints": [
            _p(r"%SystemRoot%\System32"),
            _p(r"%LocalAppData%\Microsoft\WindowsApps"),
        ],
    },
    {
        "name": "Microsoft Store",
        "category": "System",
        "exe_name": "winstore.app.exe",
        "root_folder_hints": [
            _p(r"%LocalAppData%\Microsoft\WindowsApps"),
            _p(r"%ProgramFiles%\WindowsApps\Microsoft.WindowsStore*"),
        ],
    },
]


def find_app_path(app: dict):
    """
    Try each hint path for the given app dict.
    Handles wildcard paths via glob.
    Returns {'root': str, 'exe': str} if found, else None.
    """
    exe_name = app.get("exe_name", "")
    for hint in app.get("root_folder_hints", []):
        # Expand wildcards
        if "*" in hint:
            matches = glob.glob(hint)
            candidates = sorted(matches, reverse=True)  # prefer newer versions
        else:
            candidates = [hint]

        for folder in candidates:
            if not os.path.isdir(folder):
                continue
            exe_path = os.path.join(folder, exe_name)
            if os.path.isfile(exe_path):
                return {"root": folder, "exe": exe_path}

    return None


def find_main_exe_in_folder(folder_path: str):
    """
    Scan folder_path (root and one level deep) for .exe files.
    Score them by size and name quality; return the best candidate.
    """
    if not os.path.isdir(folder_path):
        return None

    folder_name = os.path.basename(folder_path).lower()

    PENALTY_WORDS = {
        "setup", "install", "uninstall", "update", "crash", "helper",
        "updater", "repair", "redist", "vc_redist", "vcredist", "cleanup",
        "unins", "uninst", "patch",
    }

    candidates = []

    def _scan(directory: str) -> None:
        try:
            for entry in os.scandir(directory):
                if entry.is_file() and entry.name.lower().endswith(".exe"):
                    try:
                        size = entry.stat().st_size
                    except OSError:
                        size = 0
                    candidates.append((entry.path, entry.name, size))
        except PermissionError:
            pass

    _scan(folder_path)
    # One level deep
    try:
        for entry in os.scandir(folder_path):
            if entry.is_dir():
                _scan(entry.path)
    except PermissionError:
        pass

    if not candidates:
        return None

    def score(item: tuple) -> float:
        path, name, size = item
        name_lower = name.lower().replace(".exe", "")
        pts = size / (1024 * 1024)  # MB-based base score

        # Bonus: exe name contains folder name
        if folder_name and folder_name in name_lower:
            pts += 50

        # Penalty: contains bad words
        for word in PENALTY_WORDS:
            if word in name_lower:
                pts -= 200
                break

        return pts

    best = max(candidates, key=score)
    if score(best) < -100:
        # All candidates are penalty items — return None
        return None
    return best[0]
