# -*- coding: utf-8 -*-

import config
import pytest
from cmd_arg import parse_cmd
from media_platform.tieba import TieBaCrawler


@pytest.mark.asyncio
async def test_tieba_detail_cli_sets_specified_ids():
    await parse_cmd(
        [
            "--platform",
            "tieba",
            "--type",
            "detail",
            "--specified_id",
            "https://tieba.baidu.com/p/10451142633,9835114923",
        ]
    )

    assert config.TIEBA_SPECIFIED_ID_LIST == ["10451142633", "9835114923"]


@pytest.mark.asyncio
async def test_tieba_creator_cli_sets_creator_urls():
    await parse_cmd(
        [
            "--platform",
            "tieba",
            "--type",
            "creator",
            "--creator_id",
            "tb.1.example,https://tieba.baidu.com/home/main?id=tb.1.raw",
        ]
    )

    assert config.TIEBA_CREATOR_URL_LIST == [
        "https://tieba.baidu.com/home/main?id=tb.1.example",
        "https://tieba.baidu.com/home/main?id=tb.1.raw",
    ]


@pytest.mark.asyncio
async def test_cli_overrides_cdp_runtime_options(monkeypatch):
    monkeypatch.setattr(config, "CDP_CONNECT_EXISTING", True)
    monkeypatch.setattr(config, "CDP_DEBUG_PORT", 9222)

    result = await parse_cmd(
        [
            "--platform",
            "xhs",
            "--cdp_connect_existing",
            "false",
            "--cdp_debug_port",
            "9333",
        ]
    )

    assert config.CDP_CONNECT_EXISTING is False
    assert config.CDP_DEBUG_PORT == 9333
    assert result.cdp_connect_existing is False
    assert result.cdp_debug_port == 9333


@pytest.mark.asyncio
async def test_xhs_cli_sets_search_sort_type(monkeypatch):
    monkeypatch.setattr(config, "SORT_TYPE", "time_descending")

    result = await parse_cmd(
        [
            "--platform",
            "xhs",
            "--type",
            "search",
            "--sort_type",
            "popularity_descending",
        ]
    )

    assert config.SORT_TYPE == "popularity_descending"
    assert result.sort_type == "popularity_descending"


@pytest.mark.asyncio
async def test_cli_sets_max_notes_count(monkeypatch):
    monkeypatch.setattr(config, "CRAWLER_MAX_NOTES_COUNT", 15)

    result = await parse_cmd(
        [
            "--platform",
            "xhs",
            "--type",
            "search",
            "--max_notes_count",
            "40",
        ]
    )

    assert config.CRAWLER_MAX_NOTES_COUNT == 40
    assert result.max_notes_count == 40


@pytest.mark.asyncio
async def test_tieba_detail_reads_runtime_specified_ids(monkeypatch):
    crawler = TieBaCrawler()
    seen_note_ids = []

    async def fake_get_note_detail(note_id, semaphore):
        seen_note_ids.append(note_id)
        return None

    async def fake_batch_get_comments(note_details):
        return None

    monkeypatch.setattr(config, "TIEBA_SPECIFIED_ID_LIST", ["10451142633"])
    monkeypatch.setattr(crawler, "get_note_detail_async_task", fake_get_note_detail)
    monkeypatch.setattr(crawler, "batch_get_note_comments", fake_batch_get_comments)

    await crawler.get_specified_notes()

    assert seen_note_ids == ["10451142633"]
