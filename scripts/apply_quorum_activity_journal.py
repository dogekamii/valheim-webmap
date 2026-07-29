#!/usr/bin/env python3
"""One-time branch-local mechanical patch; used because the GitHub MCP only writes whole files."""
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"expected source anchor missing: {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    Path("WebMap/Config.cs"),
    "        public static bool TEST = false;\n",
    "        public static bool TEST = false;\n        public static bool QUORUM_ACTIVITY_JOURNAL_ENABLED = false;\n",
)
replace_once(
    Path("WebMap/Config.cs"),
    "            DEBUG = config.Bind(\"Server\", \"test\",\n                WebMapConfig.TEST,\n                \"Enable test features (bugs).\").Value;\n",
    "            DEBUG = config.Bind(\"Server\", \"test\",\n                WebMapConfig.TEST,\n                \"Enable test features (bugs).\").Value;\n\n            QUORUM_ACTIVITY_JOURNAL_ENABLED = config.Bind(\"Quorum Bot\", \"activity_journal_enabled\",\n                WebMapConfig.QUORUM_ACTIVITY_JOURNAL_ENABLED,\n                \"Append private local player join/leave events for the separate Valheim Quorum Bot.\").Value;\n",
)
replace_once(
    Path("WebMap/WebMap.cs"),
    "            discordWebHook.SendMessage($\"🎮 **{serverInfo[\"serverName\"]}** {message}\");\n            mapDataServer.AddMessage(peer.m_uid, (int)Talker.Type.Normal, \"Server\", message);\n",
    "            discordWebHook.SendMessage($\"🎮 **{serverInfo[\"serverName\"]}** {message}\");\n            QuorumActivityJournal.AppendJoin(peer);\n            mapDataServer.AddMessage(peer.m_uid, (int)Talker.Type.Normal, \"Server\", message);\n",
)
replace_once(
    Path("WebMap/WebMap.cs"),
    "            discordWebHook.SendMessage($\"🎮 **{serverInfo[\"serverName\"]}** {message}\");\n            MessageHud.instance.MessageAll(MessageHud.MessageType.Center, message);\n",
    "            discordWebHook.SendMessage($\"🎮 **{serverInfo[\"serverName\"]}** {message}\");\n            QuorumActivityJournal.AppendLeave(peer);\n            MessageHud.instance.MessageAll(MessageHud.MessageType.Center, message);\n",
)
