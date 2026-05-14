import pytest
from app.history_parser import HistoryParser

def test_history_parser_parse():
    parser = HistoryParser()
    history = [
        ["What is a rabbit?", "Rabbits are..."],
        ["Tell me about burrows", "Burrows are..."],
        ["What do they eat?", "They eat..."]
    ]
    topics = parser.parse(history)
    assert topics == ["What is a rabbit?", "Tell me about burrows", "What do they eat?"]

def test_history_parser_format_for_prompt():
    parser = HistoryParser()
    history = [
        ["Topic A", "Response A"]
    ]
    formatted = parser.format_for_prompt(history)
    assert "Turn 1" in formatted
    assert "Topic A" in formatted
    assert "Response A" in formatted

def test_history_parser_empty():
    parser = HistoryParser()
    assert parser.parse([]) == []
    assert parser.format_for_prompt([]) == ""
