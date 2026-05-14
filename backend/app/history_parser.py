from typing import List


class HistoryParser:
    def parse(self, history: List[dict]) -> List[str]:
        """Extract user query strings from a flat list of {role, content} dicts."""
        return [m["content"] for m in history if m.get("role") == "user"]

    def format_for_prompt(self, history: List[dict]) -> str:
        """Group flat history into user/assistant pairs and format for the LLM prompt."""
        formatted = ""
        turn = 1
        i = 0
        while i < len(history):
            msg = history[i]
            if msg.get("role") == "user":
                user_text = msg["content"]
                assistant_text = ""
                if i + 1 < len(history) and history[i + 1].get("role") == "assistant":
                    assistant_text = history[i + 1]["content"][:200]
                    i += 1
                formatted += f"Turn {turn} — User asked about: {user_text}\nRabbitPedia discussed: {assistant_text}...\n\n"
                turn += 1
            i += 1
        return formatted
